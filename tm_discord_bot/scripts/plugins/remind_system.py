from config_utils import read_config_file
from datetime import datetime
from functools import partial
import threading
import asyncio

from plugins.ai_agent_client import API_FAIL_MESSAGE

WEEK_LIST = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

# 晚間話題需等 n8n 端工具抓取熱搜與頭條，比一般對話慢，逾時放寬
NIGHT_TRENDS_TIMEOUT = 120


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
                            print(f"[{self.__class__.__name__}] 找不到提醒頻道（test_channel_id），本次提醒略過")
                        else:
                            await channel.send(f"{message_content}")
            except Exception as e:
                # 任何例外都不能讓背景任務死亡，記錄後下一分鐘繼續
                print(f"[{self.__class__.__name__}] 提醒任務發生錯誤（一分鐘後繼續運作）：{e}")
            await self._sleep_until_next_minute()

    async def _run_daily_task(self, time_str, channel_key, build_message, task_label):
        """每天於指定時間執行一次的通用迴圈（早安、晚間話題共用）。

        build_message(now, time_str) 為同步（阻塞）呼叫，移到 worker 執行緒
        以免凍結事件迴圈；回傳 None 代表本次靜默跳過（不發訊息）。
        """
        target_time = datetime.strptime(time_str, "%H:%M")
        while True:
            try:
                now = datetime.now()
                if now.hour == target_time.hour and now.minute == target_time.minute:
                    loop = asyncio.get_running_loop()
                    content = await loop.run_in_executor(
                        self.executor, partial(build_message, now, time_str)
                    )
                    if content is not None:
                        channel = self.client.get_channel(self.config.get(channel_key))
                        if channel is None:
                            print(f"[{self.__class__.__name__}] 找不到頻道（{channel_key}），本次{task_label}略過")
                        else:
                            await channel.send(f"{content}")
            except Exception as e:
                # 任何例外都不能讓背景任務死亡，記錄後下一分鐘繼續
                print(f"[{self.__class__.__name__}] {task_label}任務發生錯誤（一分鐘後繼續運作）：{e}")
            # 睡到下一分鐘整點
            await self._sleep_until_next_minute()

    def __get_morning_greeting(self, now, time_str):
        question = f"""早安，現在時間是{WEEK_LIST[now.weekday()]} {time_str}，
想請妳給各位好虎粉一段充滿活力的招呼語！不用特別提到虎喵，妳只需祝福好虎粉就好✨
每天的招呼語跟 emoji 記得都要有變化，請生成大約 60 個臺灣繁體中文字元左右。"""
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
        answer = self.ai_agent.ask(
            question=question,
            user_id="night-trends",
            channel_id="night-trends",
            timeout=NIGHT_TRENDS_TIMEOUT,
        )
        if answer == API_FAIL_MESSAGE:
            # 晚間話題屬錦上添花的推播：來源故障時靜默跳過，不在閒聊頻道貼降級訊息
            print(f"[{self.__class__.__name__}] 晚間話題取得失敗，今晚靜默跳過")
            return None
        return answer

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
        # self._tasks.append(asyncio.ensure_future(self._remind_message("14:42", "測試用", [0, 1, 2, 3, 4])))
