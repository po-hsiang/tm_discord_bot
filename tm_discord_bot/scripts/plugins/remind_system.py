from config_utils import read_config_file
from datetime import datetime
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

    def __init__(self, client, chat_gpt, yt_song_chooser) -> None:
        if not hasattr(self, "initialized"):
            self.initialized = True

            # 初始化工作，以下這區塊只會執行一次
            self.client = client
            self.chat_gpt = chat_gpt
            self.yt_song_chooser = yt_song_chooser
            self.already_started = False  # 用來記錄是否已啟動過
            self.config = read_config_file()

    async def _remind_message(self, time_str, message_content, weekdays=None):
        target_time = datetime.strptime(time_str, "%H:%M")
        while True:
            now = datetime.now()
            if weekdays is None or now.weekday() in weekdays:
                if now.hour == target_time.hour and now.minute == target_time.minute:
                    channel = self.client.get_channel(
                        self.config.get("test_channel_id")
                    )
                    await channel.send(f"{message_content}")
            await asyncio.sleep(60)

    async def _send_morning_call(self, time_str):
        while True:
            now = datetime.now()
            target_time = datetime.strptime(time_str, "%H:%M")
            if now.hour == target_time.hour and now.minute == target_time.minute:
                # 取得每日不同的招呼語
                morning_greeting = self.__get_morning_greeting(now.weekday(), time_str)
                channel = self.client.get_channel(
                    self.config.get("chitchat_channel_id")
                )
                await channel.send(f"{morning_greeting}")
            # 暫停 1 分鐘
            await asyncio.sleep(60)

    def __get_morning_greeting(self, weekday, time_str):
        week_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        question = f"早安，現在時間是{week_list[weekday]}{time_str}，你可以給各位好虎粉一個熱情且活力的早安招呼語嗎？不用特別提到虎喵，你只需祝福好虎粉就好，請用40字以內回答"
        answer = self.chat_gpt.ask_question(question=question)
        song = self.yt_song_chooser.choose_one_song()
        morning_greeting = f"{answer}\n最後為大家送上本日好歌推推： \n {song} "
        return morning_greeting

    def start(self):
        if self.already_started:
            return
        self.already_started = True
        asyncio.ensure_future(self._send_morning_call("7:30"))
        # asyncio.ensure_future(self._remind_message("14:42", "測試用", [0, 1, 2, 3, 4]))
