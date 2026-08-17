"""排程引擎：負責「什麼時候跑」，完全不知道推播的內容是什麼。

可靠度由 storage 層的執行紀錄提供，分成兩件事：

* **不重複發**：發送前先「認領」今天這一則，認領不到就略過。
  斷線重連、容器重啟、同時跑起兩個實例，都不會讓好虎粉收到兩次早安。
* **開機補發**：啟動時若發現今天的推播時刻已過卻沒有成功紀錄，就補發一次。
  容器在 07:20 重開、08:00 才起來，早安不會整天消失。

沒有持久化時（未設定 MongoDB）兩者自動退化：照常按時推播，
但不做防重複、也不補發——因為沒有紀錄就無從判斷「發過了沒」。
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial

from tm_bot.storage.schedule_runs import ScheduleRunRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledJob:
    """一則定時推播的定義。

    build(now, time_str) 為同步（阻塞）呼叫，由引擎丟到執行緒池執行；
    回傳 None 代表本次靜默跳過（不發訊息）。
    weekdays 為 None＝每天執行，(4,)＝只在星期五執行。
    catchup_hours 為開機補發的容許遲到時數（0＝不補發）；
    補發一律不跨日，過了午夜就當作錯過。
    """

    label: str
    time_str: str
    channel_key: str
    build: Callable
    weekdays: tuple | None = None
    catchup_hours: int = 3


def is_due(now, target_time, weekdays):
    """判斷 now 是否命中排程時刻；weekdays 為星期過濾（0=一，None=每天）。"""
    if weekdays is not None and now.weekday() not in weekdays:
        return False
    return now.hour == target_time.hour and now.minute == target_time.minute


def catch_up_delay(now, target_time, weekdays, catchup_hours):
    """開機時判斷「今天這則該不該補發」，回傳已遲多久；不該補發則回傳 None。

    只看時間規則，不查紀錄——「是否已經發過」由 ScheduleRunRepository 判定，
    兩者分開才能各自單獨測試。

    補發不跨日是刻意的：過了午夜之後，今天的 target 會落在未來（now <= target），
    自然就不補了，不必另外寫跨日判斷。
    """
    if catchup_hours <= 0:
        return None
    if weekdays is not None and now.weekday() not in weekdays:
        return None

    target = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if now <= target:
        return None  # 今天還沒到時間，交給正常排程

    late_by = now - target
    if late_by > timedelta(hours=catchup_hours):
        return None  # 遲太久了，這時候才補反而突兀
    return late_by


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

    def __init__(self, client, settings, executor=None, runs=None):
        self.client = client
        self.settings = settings
        # 阻塞的 AI／歌單／Mongo 呼叫丟到執行緒池，不凍結事件迴圈
        self.executor = executor
        # 未提供時給一個停用狀態的紀錄庫：呼叫端不必到處判斷 None
        self.runs = runs if runs is not None else ScheduleRunRepository(None)
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
            "排程已啟動：%s（防重複與開機補發：%s）",
            "、".join(f"{job.label} {job.time_str}" for job in self._jobs),
            "啟用" if self.runs.enabled else "停用，未設定 MongoDB",
        )

    async def _run(self, job):
        target_time = datetime.strptime(job.time_str, "%H:%M")
        # 排程在 setup_hook 就啟動（早於 Gateway 連線），先等頻道快取就緒再開始輪詢
        await self.client.wait_until_ready()

        try:
            await self._catch_up(job, target_time)
        except Exception:
            # 補發失敗不能連累常態排程，記錄後照常進入輪詢
            logger.exception("%s開機補發檢查失敗（不影響後續排程）", job.label)

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
        await self._dispatch(job, now, job.time_str)

    async def _catch_up(self, job, target_time):
        """啟動時補上今天漏掉的推播。"""
        if not self.runs.enabled:
            # 沒有紀錄就無從判斷發過沒，硬補等於每次重啟都洗版
            return

        now = datetime.now()
        late_by = catch_up_delay(now, target_time, job.weekdays, job.catchup_hours)
        if late_by is None:
            return

        logger.info(
            "檢查%s是否漏發（原定 %s，現已遲 %d 分鐘）",
            job.label,
            job.time_str,
            int(late_by.total_seconds() // 60),
        )
        # 補發時如實告知「現在幾點」，訊息才不會宣稱自己是七點半發的。
        # fail_open=False：Mongo 這時候剛好不通就別補了，寧可漏發也不要重複發。
        await self._dispatch(job, now, f"{now.hour}:{now.minute:02d}", fail_open=False)

    async def _dispatch(self, job, now, time_str, fail_open=True):
        """認領 → 產生內容 → 發送 → 記錄。回傳是否真的發出了訊息。"""
        day = now.date()
        if not await self._run_blocking(self.runs.claim, job.label, day, fail_open):
            logger.info("%s今日（%s）已處理過，略過本次", job.label, day)
            return False

        try:
            content = await self._build_and_send(job, now, time_str)
        except Exception:
            # 沒發成就把認領還回去，讓稍後的開機補發還有機會重試
            await self._run_blocking(self.runs.release, job.label, day)
            raise

        if content is None:
            await self._run_blocking(self.runs.release, job.label, day)
            return False

        await self._run_blocking(self.runs.mark_sent, job.label, day, len(content))
        return True

    async def _build_and_send(self, job, now, time_str):
        """產生內容並送出；靜默跳過或找不到頻道時回傳 None。"""
        content = await self._run_blocking(job.build, now, time_str)
        if content is None:
            return None

        channel = self.client.get_channel(self.settings.channel_id(job.channel_key))
        if channel is None:
            logger.warning("找不到頻道（%s），本次%s略過", job.channel_key, job.label)
            return None

        await channel.send(f"{content}")
        # 成功也留一筆：docker logs 即可稽核排程健康度，不用翻 Discord
        logger.info("%s已發送（%d 字元）", job.label, len(content))
        return content

    async def _run_blocking(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, partial(func, *args))
