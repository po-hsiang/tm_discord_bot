from config_utils import read_config_file
from datetime import datetime
from functools import partial
import threading
import asyncio


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

    async def _send_morning_call(self, time_str):
        target_time = datetime.strptime(time_str, "%H:%M")
        while True:
            try:
                now = datetime.now()
                if now.hour == target_time.hour and now.minute == target_time.minute:
                    # GPT 與歌單為同步（阻塞）呼叫，移到 worker 執行緒以免凍結事件迴圈
                    loop = asyncio.get_running_loop()
                    morning_greeting = await loop.run_in_executor(
                        self.executor,
                        partial(self.__get_morning_greeting, now.weekday(), time_str),
                    )
                    channel = self.client.get_channel(
                        self.config.get("chitchat_channel_id")
                    )
                    if channel is None:
                        print(f"[{self.__class__.__name__}] 找不到閒聊頻道（chitchat_channel_id），本次早安略過")
                    else:
                        await channel.send(f"{morning_greeting}")
            except Exception as e:
                # 任何例外都不能讓早安任務死亡，記錄後下一分鐘繼續
                print(f"[{self.__class__.__name__}] 早安任務發生錯誤（一分鐘後繼續運作）：{e}")
            # 睡到下一分鐘整點
            await self._sleep_until_next_minute()

    def __get_morning_greeting(self, weekday, time_str):
        week_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        question = f"""早安，現在時間是{week_list[weekday]} {time_str}，
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

    def start(self):
        if self.already_started:
            return
        self.already_started = True
        self._tasks.append(asyncio.ensure_future(self._send_morning_call("7:30")))
        # self._tasks.append(asyncio.ensure_future(self._remind_message("14:42", "測試用", [0, 1, 2, 3, 4])))
