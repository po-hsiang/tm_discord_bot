from config_utils import read_config_file
from datetime import datetime
from functools import partial
import asyncio
import logging
import threading
import time

from plugins.ai_agent_client import API_FAIL_MESSAGE
from plugins.holiday_lookup import KIND_MAKEUP, get_holiday_info

logger = logging.getLogger(__name__)

WEEK_LIST = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 帶工具的排程任務需等 n8n 端抓取外部資料，比一般對話慢，逾時放寬
NIGHT_TRENDS_TIMEOUT = 120
GAME_DEALS_TIMEOUT = 120
# 首次失敗後的重試間隔：留給 n8n／LLM 足夠的緩衝喘息，不急著連打
AI_RETRY_DELAY = 60
# n8n 端 game_deals 工具雙來源皆故障時的哨兵字串（排程 Prompt 要求 AI 原樣回覆）
GAME_DEALS_SENTINEL = "GAME_DEALS_UNAVAILABLE"


class RemindSystem:
    _instance = None
    _lock = threading.Lock()

    # Singleton Pattern
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RemindSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self, client, ai_agent, yt_song_chooser, executor=None) -> None:
        if not hasattr(self, "initialized"):
            self.initialized = True

            # 初始化工作，以下這區塊只會執行一次
            self.client = client
            self.ai_agent = ai_agent
            self.yt_song_chooser = yt_song_chooser
            # 與指令處理共用同一個單執行緒 worker，
            # 阻塞的 GPT／歌單呼叫不會凍結事件迴圈，共享狀態也維持序列化存取
            self.executor = executor
            self.already_started = False  # 用來記錄是否已啟動過
            self._tasks = []  # 保留背景任務參考，避免被垃圾回收
            self.config = read_config_file()

    @staticmethod
    async def _sleep_until_next_minute():
        # 睡到「下一分鐘整點」再醒來，取代固定 sleep(60)：
        # 固定間隔會因處理耗時累積漂移，可能整分鐘跳過目標時間（如 07:30）
        now = datetime.now()
        seconds_to_next_minute = 60 - now.second - now.microsecond / 1_000_000
        await asyncio.sleep(seconds_to_next_minute + 0.05)

    async def _remind_message(self, time_str, message_content, weekdays=None):
        target_time = datetime.strptime(time_str, "%H:%M")
        while True:
            try:
                now = datetime.now()
                if weekdays is None or now.weekday() in weekdays:
                    if now.hour == target_time.hour and now.minute == target_time.minute:
                        channel = self.client.get_channel(
                            self.config.get("test_channel_id")
                        )
                        if channel is None:
                            logger.warning("找不到提醒頻道（test_channel_id），本次提醒略過")
                        else:
                            await channel.send(f"{message_content}")
            except Exception:
                # 任何例外都不能讓背景任務死亡，記錄後下一分鐘繼續
                logger.exception("提醒任務發生錯誤（一分鐘後繼續運作）")
            await self._sleep_until_next_minute()

    @staticmethod
    def _is_due(now, target_time, weekdays):
        """判斷 now 是否命中排程時刻；weekdays 為星期過濾（0=一，None=每天）。"""
        if weekdays is not None and now.weekday() not in weekdays:
            return False
        return now.hour == target_time.hour and now.minute == target_time.minute

    async def _run_daily_task(self, time_str, channel_key, build_message, task_label, weekdays=None):
        """於指定時間執行的通用迴圈（早安、晚間話題、遊戲情報共用）。

        build_message(now, time_str) 為同步（阻塞）呼叫，移到 worker 執行緒
        以免凍結事件迴圈；回傳 None 代表本次靜默跳過（不發訊息）。
        weekdays 不傳＝每天執行，傳 [4]＝只在星期五執行。
        """
        target_time = datetime.strptime(time_str, "%H:%M")
        while True:
            try:
                now = datetime.now()
                if self._is_due(now, target_time, weekdays):
                    loop = asyncio.get_running_loop()
                    content = await loop.run_in_executor(
                        self.executor, partial(build_message, now, time_str)
                    )
                    if content is not None:
                        channel = self.client.get_channel(self.config.get(channel_key))
                        if channel is None:
                            logger.warning("找不到頻道（%s），本次%s略過", channel_key, task_label)
                        else:
                            await channel.send(f"{content}")
                            # 成功也留一筆：docker logs 即可稽核排程健康度，不用翻 Discord
                            logger.info("%s已發送（%d 字元）", task_label, len(content))
            except Exception:
                # 任何例外都不能讓背景任務死亡，記錄後下一分鐘繼續
                logger.exception("%s任務發生錯誤（一分鐘後繼續運作）", task_label)
            # 睡到下一分鐘整點
            await self._sleep_until_next_minute()

    @staticmethod
    def _build_holiday_line(now):
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
            return f"今天是「{name}」連假的補假日！請體恤大家連假出遊，聊聊塞車、去哪玩之類的話題。\n"
        return f"今天是「{name}」！請把節日彩蛋自然融入招呼語（應景祝福或節日梗），節日感要明顯。\n"

    def __get_morning_greeting(self, now, time_str):
        question = f"""早安，現在時間是{WEEK_LIST[now.weekday()]} {time_str}，
想請妳給各位好虎粉一段充滿活力的招呼語！不用特別提到虎喵，妳只需祝福好虎粉就好✨
{self._build_holiday_line(now)}接著請用 tw_weather 工具取得臺灣今日總體天氣，用一兩句話播報重點並附上貼心提醒
（如帶傘、防曬、保暖），自然融入訊息、不要像制式氣象報告；若天氣暫時取不到就略過、照常打招呼。
每天的招呼語跟 emoji 記得都要有變化，全篇約 100 個臺灣繁體中文字元左右。"""
        # 走 n8n AI Agent，並使用專屬 session（morning-call）：
        # 與各頻道聊天記憶隔離，又能看見前幾天的招呼語，利於「每天都要有變化」
        answer = self.ai_agent.ask(
            question=question,
            user_id="morning-call",
            channel_id="morning-call",
        )
        song = self.yt_song_chooser.choose_one_song()
        if song.startswith("http"):
            morning_greeting = f"{answer}\n [最後為大家送上本日好歌推推]({song}) "
        else:
            # 歌單載入失敗時的降級訊息，不套 Markdown 連結格式
            morning_greeting = f"{answer}\n {song}"
        return morning_greeting

    def __get_night_trends(self, now, time_str):
        question = f"""現在是{WEEK_LIST[now.weekday()]}晚上七點半的「今晚話題」時間！
請用 tw_trends_news 工具取得台灣目前的熱搜與頭條，幫頻道的好虎粉「劃重點」：
1. 完全排除政治相關內容（政黨、選舉、政治人物、政策攻防、兩岸政治等），遇到就跳過不提。
2. 兇殺、輕生等悲劇社會案件也跳過不提。
3. 優先挑娛樂、遊戲、動漫、科技、生活、體育類，選出 2～4 個最有梗的話題。
4. 格式：不要開場問候、也不要結尾的互動邀請；第一行用一句話點出今晚熱搜的整體氛圍，
接著每個話題獨立一行，以貼切的 emoji 開頭，寫成「話題：一句話重點或吐槽」。
5. 語氣像臺灣的活網仔／鄉民，可自然使用網路流行語，但不低俗、不嘲諷或攻擊任何人。
6. 若過濾後沒剩什麼可聊的，就用一句話老實說今晚熱搜比較嚴肅，再自起一個輕鬆話題。
7. 內容記得跟前幾晚做出變化，全篇 150 個臺灣繁體中文字元以內。"""
        # 專屬 session（night-trends）：與各頻道記憶隔離，又能看見前幾晚貼過的話題
        return self._ask_with_retry(question, "night-trends", NIGHT_TRENDS_TIMEOUT, "晚間話題")

    def __get_game_deals(self, now, time_str):
        question = """現在是星期五晚上十點的「週末遊戲情報」時間！
請用 game_deals 工具取得本週遊戲特惠，幫【遊戲約約】頻道的好虎粉整理：
1. Epic 部分：只報「本週免費」的遊戲（附免費領取截止日），下週預告與更遠的項目都不要提。
2. Steam 部分：從特惠中挑「折扣 50% 以上、或知名大作」，精選 3～5 款，附折扣與台幣價格。
3. 格式：不要開場問候、也不要結尾的互動邀請；第一行用一句話總結本週值不值得掏錢包，
接著每款遊戲獨立一行，以貼切的 emoji 開頭，寫成「遊戲名：一句話重點（折扣或價格）」。
4. 遊戲名請寫成 Markdown 超連結 [遊戲名](<網址>)：網址一律原樣複製工具提供的「連結」，
不可自行改寫或猜測；工具沒提供連結的遊戲就只寫名稱。網址外層的角括號 <> 務必保留。
5. 語氣像臺灣的活網仔／鄉民，可自然使用網路流行語（快領、錢包不保），但不低俗。
6. 若工具回報 GAME_DEALS_UNAVAILABLE 或特惠資料取不到，請只回覆 GAME_DEALS_UNAVAILABLE，
不要加任何其他文字。
7. 全篇 200 個臺灣繁體中文字元以內（網址不計入字數）。"""
        # 專屬 session（game-deals）：與各頻道記憶隔離，也讓每週的吐槽有變化
        answer = self._ask_with_retry(question, "game-deals", GAME_DEALS_TIMEOUT, "遊戲情報")
        if answer is not None and GAME_DEALS_SENTINEL in answer:
            # 工具雙來源皆故障：AI 依指示原樣回覆哨兵字串，本週靜默跳過
            logger.warning("遊戲情報來源故障（哨兵字串），本週靜默跳過")
            return None
        return answer

    def _ask_with_retry(self, question, session, timeout, task_label):
        """呼叫 AI Agent（專屬 session），失敗時隔 AI_RETRY_DELAY 秒重試一次。

        排程推播一天只有一次機會，偶發故障（逾時、瞬斷）值得多試一次；
        發送動作在 _run_daily_task 只會執行一次，重試不會造成重複貼文。
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

    def start(self):
        if self.already_started:
            return
        self.already_started = True
        self._tasks.append(asyncio.ensure_future(
            self._run_daily_task("7:30", "chitchat_channel_id", self.__get_morning_greeting, "早安")
        ))
        self._tasks.append(asyncio.ensure_future(
            self._run_daily_task("19:30", "chitchat_channel_id", self.__get_night_trends, "晚間話題")
        ))
        self._tasks.append(asyncio.ensure_future(
            self._run_daily_task(
                "22:00", "game_deals_channel_id", self.__get_game_deals, "遊戲情報", weekdays=[4]
            )
        ))
        # self._tasks.append(asyncio.ensure_future(self._remind_message("14:42", "測試用", [0, 1, 2, 3, 4])))
