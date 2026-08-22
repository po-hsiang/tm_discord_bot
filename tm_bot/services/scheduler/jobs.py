"""排程推播的內容產生：負責「內容是什麼」，不知道自己何時會被呼叫。

三個產生器都是同步（阻塞）呼叫，由 runner 丟到執行緒池執行；
回傳 None 代表本次靜默跳過（不在頻道貼降級訊息）。
"""

import logging
import re
import time

from tm_bot.clients.ai_agent import API_FAIL_MESSAGE
from tm_bot.services.holiday import KIND_MAKEUP, get_holiday_info
from tm_bot.services.scheduler import prompts
from tm_bot.services.scheduler.runner import ScheduledJob

logger = logging.getLogger(__name__)

# 帶工具的排程任務需等 n8n 端抓取外部資料，比一般對話慢，逾時放寬
NIGHT_TRENDS_TIMEOUT = 120
GAME_DEALS_TIMEOUT = 120
# 首次失敗後的重試間隔：留給 n8n／LLM 足夠的緩衝喘息，不急著連打
AI_RETRY_DELAY = 60

# 平台標籤：「網域 → 標籤」。刻意由程式判斷而非請 AI 標記——
# 平台是從連結網域就能確定的事實，交給模型只是多一個會出錯的地方
PLATFORM_TAGS = (
    ("steampowered.com", "【Steam】"),
    ("epicgames.com", "【Epic】"),
)

# 抓行內第一個 Markdown 連結的網址（角括號可有可無）
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(<?(?P<url>https?://[^\s)>]+?)>?\)")


def tag_platforms(text):
    """在每一行遊戲的最前面補上【Steam】／【Epic】標籤。

    判斷依據是該行 Markdown 連結的網域。認不出平台的行（開場總結那句、
    或工具沒給連結而只寫了名稱的遊戲）原樣保留——寧可少一個標籤，
    也不要猜錯平台。
    """
    if not text:
        return text
    tagged = []
    for line in text.splitlines():
        match = _MARKDOWN_LINK.search(line)
        tag = _platform_tag(match.group("url")) if match else None
        tagged.append(f"{tag} {line}" if tag else line)
    return "\n".join(tagged)


def _platform_tag(url):
    host = url.split("/")[2].lower() if "://" in url else ""
    for domain, tag in PLATFORM_TAGS:
        # 比對到網域邊界，evilsteampowered.com 這種山寨網域不會誤判成 Steam
        if host == domain or host.endswith(f".{domain}"):
            return tag
    return None


class ScheduledMessages:
    """三則排程訊息的內容產生器。"""

    def __init__(self, ai_agent, yt_song_chooser):
        self.ai_agent = ai_agent
        self.yt_song_chooser = yt_song_chooser

    def morning_greeting(self, now, time_str):
        question = prompts.morning_greeting(now, time_str, self._holiday_line(now))
        # 走 n8n AI Agent，並使用專屬 session（morning-call）：
        # 與各頻道聊天記憶隔離，又能看見前幾天的招呼語，利於「每天都要有變化」
        answer = self.ai_agent.ask(
            question=question,
            user_id="morning-call",
            channel_id="morning-call",
        )
        song = self.yt_song_chooser.choose_one_song()
        if song.startswith("http"):
            return f"{answer}\n [最後為大家送上本日好歌推推]({song}) "
        # 歌單載入失敗時的降級訊息，不套 Markdown 連結格式
        return f"{answer}\n {song}"

    def night_trends(self, now, time_str):
        # 專屬 session（night-trends）：與各頻道記憶隔離，又能看見前幾晚貼過的話題
        return self._ask_with_retry(
            prompts.night_trends(now), "night-trends", NIGHT_TRENDS_TIMEOUT, "晚間話題"
        )

    def game_deals(self, now, time_str):
        # 專屬 session（game-deals）：與各頻道記憶隔離，也讓每週的吐槽有變化
        answer = self._ask_with_retry(
            prompts.game_deals(), "game-deals", GAME_DEALS_TIMEOUT, "遊戲情報"
        )
        if answer is None:
            return None
        if prompts.GAME_DEALS_SENTINEL in answer:
            # 工具雙來源皆故障：AI 依指示原樣回覆哨兵字串，本週靜默跳過
            logger.warning("遊戲情報來源故障（哨兵字串），本週靜默跳過")
            return None
        return tag_platforms(answer)

    @staticmethod
    def _holiday_line(now):
        """今天若是節日或補假，回傳早安 Prompt 的彩蛋指示（含換行）；平日回傳空字串。

        查詢是本地離線計算，仍防禦性包一層：彩蛋失敗不能拖垮整則早安。
        """
        try:
            info = get_holiday_info(now.date())
        except Exception:
            logger.exception("節日查詢失敗，本日照常打招呼（無彩蛋）")
            return ""
        if info is None:
            return ""
        kind, name = info
        if kind == KIND_MAKEUP:
            return prompts.makeup_holiday_line(name)
        return prompts.festival_line(name)

    def _ask_with_retry(self, question, session, timeout, task_label):
        """呼叫 AI Agent（專屬 session），失敗時隔 AI_RETRY_DELAY 秒重試一次。

        排程推播一天只有一次機會，偶發故障（逾時、瞬斷）值得多試一次；
        發送動作在 runner 只會執行一次，重試不會造成重複貼文。
        重試仍失敗回傳 None（呼叫端靜默跳過，不在頻道貼降級訊息）。
        """
        for attempt in range(2):
            answer = self.ai_agent.ask(
                question=question,
                user_id=session,
                channel_id=session,
                timeout=timeout,
            )
            if answer != API_FAIL_MESSAGE:
                return answer
            if attempt == 0:
                logger.warning("%s第一次取得失敗，%d 秒後重試一次", task_label, AI_RETRY_DELAY)
                time.sleep(AI_RETRY_DELAY)
        logger.warning("%s重試後仍失敗，本次靜默跳過", task_label)
        return None


def build_jobs(ai_agent, yt_song_chooser):
    """本專案的排程表——要加、要改推播時間，動這裡就好。

    catchup_hours 是「開機補發的容許遲到時數」：機器人若在推播時刻沒開著，
    啟動後只要還在這個時窗內就補發一次，超過就當作錯過（遲到太久反而突兀）。
    補發不跨日，所以 22:00 的遊戲情報實際補到當天 23:59 為止。
    """
    messages = ScheduledMessages(ai_agent, yt_song_chooser)
    return (
        # 早安補到 10:30——過了上午再說早安就怪了
        ScheduledJob(
            "早安", "7:30", "chitchat_channel_id", messages.morning_greeting, catchup_hours=3
        ),
        # 晚間話題補到 22:30，還在大家掛在線上的時段
        ScheduledJob(
            "晚間話題", "19:30", "chitchat_channel_id", messages.night_trends, catchup_hours=3
        ),
        ScheduledJob(
            "遊戲情報",
            "22:00",
            "game_deals_channel_id",
            messages.game_deals,
            weekdays=(4,),
            catchup_hours=2,
        ),
    )
