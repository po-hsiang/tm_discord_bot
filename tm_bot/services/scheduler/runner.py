"""排程引擎：負責「什麼時候跑」，完全不知道推播的內容是什麼。"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledJob:
    """一則定時推播的定義。

    build(now, time_str) 為同步（阻塞）呼叫，由引擎丟到執行緒池執行；
    回傳 None 代表本次靜默跳過（不發訊息）。
    weekdays 為 None＝每天執行，(4,)＝只在星期五執行。
    """

    label: str
    time_str: str
    channel_key: str
    build: Callable
    weekdays: tuple | None = None


def is_due(now, target_time, weekdays):
    """判斷 now 是否命中排程時刻；weekdays 為星期過濾（0=一，None=每天）。"""
    if weekdays is not None and now.weekday() not in weekdays:
        return False
    return now.hour == target_time.hour and now.minute == target_time.minute


async def sleep_until_next_minute():
    # 睡到「下一分鐘整點」再醒來，取代固定 sleep(60)：
    # 固定間隔會因處理耗時累積漂移，可能整分鐘跳過目標時間（如 07:30）
    now = datetime.now()
    seconds_to_next_minute = 60 - now.second - now.microsecond / 1_000_000
    await asyncio.sleep(seconds_to_next_minute + 0.05)


class Scheduler:
    """把 ScheduledJob 變成常駐的背景任務。

    由 TmBot.setup_hook 建立並啟動；setup_hook 只在啟動時執行一次、
    斷線重連不會重跑，因此不需要額外的防重複建立機制。
    """

    def __init__(self, client, settings, executor=None):
        self.client = client
        self.settings = settings
        # 阻塞的 AI／歌單呼叫丟到執行緒池，不凍結事件迴圈
        self.executor = executor
        self.already_started = False
        self._jobs = []
        self._tasks = []  # 保留背景任務參考，避免被垃圾回收

    def add(self, *jobs):
        self._jobs.extend(jobs)
        return self

    def start(self):
        if self.already_started:
            return
        self.already_started = True
        for job in self._jobs:
            self._tasks.append(asyncio.ensure_future(self._run(job)))
        logger.info(
            "排程已啟動：%s", "、".join(f"{job.label} {job.time_str}" for job in self._jobs)
        )

    async def _run(self, job):
        target_time = datetime.strptime(job.time_str, "%H:%M")
        # 排程在 setup_hook 就啟動（早於 Gateway 連線），先等頻道快取就緒再開始輪詢
        await self.client.wait_until_ready()
        while True:
            try:
                await self._tick(job, target_time)
            except Exception:
                # 任何例外都不能讓背景任務死亡，記錄後下一分鐘繼續
                logger.exception("%s任務發生錯誤（一分鐘後繼續運作）", job.label)
            await sleep_until_next_minute()

    async def _tick(self, job, target_time):
        now = datetime.now()
        if not is_due(now, target_time, job.weekdays):
            return

        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(self.executor, partial(job.build, now, job.time_str))
        if content is None:
            return

        channel = self.client.get_channel(self.settings.channel_id(job.channel_key))
        if channel is None:
            logger.warning("找不到頻道（%s），本次%s略過", job.channel_key, job.label)
            return

        await channel.send(f"{content}")
        # 成功也留一筆：docker logs 即可稽核排程健康度，不用翻 Discord
        logger.info("%s已發送（%d 字元）", job.label, len(content))
