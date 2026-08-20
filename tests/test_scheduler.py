import unittest
from datetime import datetime, timedelta
from unittest import mock

from tests.factories import make_settings
from tm_bot.clients.ai_agent import API_FAIL_MESSAGE
from tm_bot.services.scheduler.jobs import (
    AI_RETRY_DELAY,
    GAME_DEALS_TIMEOUT,
    NIGHT_TRENDS_TIMEOUT,
    ScheduledMessages,
    build_jobs,
)
from tm_bot.services.scheduler.prompts import GAME_DEALS_SENTINEL
from tm_bot.services.scheduler.runner import (
    ScheduledJob,
    Scheduler,
    catch_up_delay,
    is_due,
)

MONDAY_NIGHT = datetime(2026, 8, 3, 22, 0)
MONDAY_MORNING = datetime(2026, 8, 3, 7, 30)
FRIDAY_NIGHT = datetime(2026, 8, 7, 22, 0)


class FakeAgent:
    def __init__(self, *replies):
        # 可傳多個回覆模擬「第一次失敗、第二次成功」；超過就重複最後一個
        self.replies = list(replies)
        self.calls = []

    def ask(self, *args, **kwargs):
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.replies) - 1)
        return self.replies[index]


class FakeSongChooser:
    def __init__(self, song):
        self.song = song

    def choose_one_song(self):
        return self.song


def make_messages(ai_agent, yt_song_chooser=None):
    return ScheduledMessages(ai_agent, yt_song_chooser)


class TestScheduleTable(unittest.TestCase):
    """排程表是對外行為（幾點發、發到哪個頻道），改動必須是刻意的。"""

    def setUp(self):
        self.jobs = {job.label: job for job in build_jobs(FakeAgent("ok"), FakeSongChooser("x"))}

    def test_three_jobs_are_scheduled(self):
        self.assertEqual(set(self.jobs), {"早安", "晚間話題", "遊戲情報"})

    def test_morning_job(self):
        job = self.jobs["早安"]
        self.assertEqual(job.time_str, "7:30")
        self.assertEqual(job.channel_key, "chitchat_channel_id")
        self.assertIsNone(job.weekdays)  # 每天
        self.assertEqual(job.catchup_hours, 3)  # 補到 10:30，過了上午說早安就怪了

    def test_night_trends_job(self):
        job = self.jobs["晚間話題"]
        self.assertEqual(job.time_str, "19:30")
        self.assertEqual(job.channel_key, "chitchat_channel_id")
        self.assertIsNone(job.weekdays)
        self.assertEqual(job.catchup_hours, 3)

    def test_game_deals_job_is_friday_only(self):
        job = self.jobs["遊戲情報"]
        self.assertEqual(job.time_str, "22:00")
        self.assertEqual(job.channel_key, "game_deals_channel_id")
        self.assertEqual(job.weekdays, (4,))  # 只在星期五
        self.assertEqual(job.catchup_hours, 2)


class TestNightTrends(unittest.TestCase):
    def test_success_uses_dedicated_session_and_timeout(self):
        agent = FakeAgent("今晚話題來囉！")

        result = make_messages(agent).night_trends(MONDAY_NIGHT, "22:00")

        self.assertEqual(result, "今晚話題來囉！")
        # 一次就成功時不會多打第二次
        self.assertEqual(len(agent.calls), 1)
        call = agent.calls[-1]
        self.assertEqual(call["user_id"], "night-trends")
        self.assertEqual(call["channel_id"], "night-trends")
        self.assertEqual(call["timeout"], NIGHT_TRENDS_TIMEOUT)

    def test_prompt_contains_tool_and_filter_rules(self):
        agent = FakeAgent("今晚話題來囉！")

        make_messages(agent).night_trends(MONDAY_NIGHT, "22:00")

        question = agent.calls[-1]["question"]
        self.assertIn("tw_trends_news", question)
        self.assertIn("排除政治", question)
        self.assertIn("刑事與悲劇案件", question)
        # 這是遊戲實況社群，ACG／Steam 優先於一般熱搜（2026-08-20 主人定案）；
        # 分流靠 n8n 回的 category 欄位，改名或拿掉都會讓優先序失效
        self.assertIn("category", question)
        self.assertIn("acg 或 steam 的最優先", question)
        self.assertIn("星期一", question)

    def test_first_failure_retries_once_and_posts_retry_answer(self):
        agent = FakeAgent(API_FAIL_MESSAGE, "重試後拿到的話題！")

        with mock.patch("tm_bot.services.scheduler.jobs.time.sleep") as fake_sleep:
            result = make_messages(agent).night_trends(MONDAY_NIGHT, "22:00")

        self.assertEqual(result, "重試後拿到的話題！")
        self.assertEqual(len(agent.calls), 2)
        # 重試前有留緩衝間隔，讓 n8n／LLM 喘息
        fake_sleep.assert_called_once_with(AI_RETRY_DELAY)

    def test_api_failure_after_retry_returns_none_for_silent_skip(self):
        agent = FakeAgent(API_FAIL_MESSAGE)

        with mock.patch("tm_bot.services.scheduler.jobs.time.sleep") as fake_sleep:
            result = make_messages(agent).night_trends(MONDAY_NIGHT, "22:00")

        self.assertIsNone(result)
        # 只重試一次（共打兩次）就放棄，避免無限重打
        self.assertEqual(len(agent.calls), 2)
        fake_sleep.assert_called_once()


class TestGameDeals(unittest.TestCase):
    def test_success_uses_dedicated_session_and_timeout(self):
        agent = FakeAgent("本週遊戲情報來囉！")

        result = make_messages(agent).game_deals(FRIDAY_NIGHT, "22:00")

        self.assertEqual(result, "本週遊戲情報來囉！")
        self.assertEqual(len(agent.calls), 1)
        call = agent.calls[-1]
        self.assertEqual(call["user_id"], "game-deals")
        self.assertEqual(call["channel_id"], "game-deals")
        self.assertEqual(call["timeout"], GAME_DEALS_TIMEOUT)

    def test_prompt_contains_tool_and_selection_rules(self):
        agent = FakeAgent("ok")

        make_messages(agent).game_deals(FRIDAY_NIGHT, "22:00")

        question = agent.calls[-1]["question"]
        self.assertIn("game_deals", question)
        # Epic 只報本週免費（下週預告可能含遠期項目，n8n 端提醒過的資料特性）
        self.assertIn("本週免費", question)
        self.assertIn("下週預告與更遠的項目都不要提", question)
        self.assertIn("折扣 50% 以上", question)
        # Markdown 連結：角括號抑制 Discord 預覽卡片；工具沒給連結時要能安全降級
        self.assertIn("[遊戲名](<網址>)", question)
        self.assertIn("原樣複製", question)
        self.assertIn("工具沒提供連結的遊戲就只寫名稱", question)
        # 哨兵指示：Agent 平常聊天會把哨兵轉成可愛回覆，排程必須要求原樣回覆才能比對
        self.assertIn("請只回覆 GAME_DEALS_UNAVAILABLE", question)

    def test_sentinel_reply_returns_none_for_silent_skip(self):
        messages = make_messages(FakeAgent(GAME_DEALS_SENTINEL))

        self.assertIsNone(messages.game_deals(FRIDAY_NIGHT, "22:00"))

    def test_api_failure_after_retry_returns_none(self):
        agent = FakeAgent(API_FAIL_MESSAGE)

        with mock.patch("tm_bot.services.scheduler.jobs.time.sleep") as fake_sleep:
            result = make_messages(agent).game_deals(FRIDAY_NIGHT, "22:00")

        self.assertIsNone(result)
        self.assertEqual(len(agent.calls), 2)
        fake_sleep.assert_called_once_with(AI_RETRY_DELAY)


class TestIsDue(unittest.TestCase):
    TARGET = datetime.strptime("22:00", "%H:%M")

    def test_friday_2200_is_due(self):
        # 2026-08-07 為星期五（weekday=4）
        self.assertTrue(is_due(FRIDAY_NIGHT, self.TARGET, (4,)))

    def test_other_weekday_is_not_due(self):
        # 2026-08-03 為星期一：時間相同但星期不符
        self.assertFalse(is_due(MONDAY_NIGHT, self.TARGET, (4,)))

    def test_none_weekdays_means_daily(self):
        self.assertTrue(is_due(MONDAY_NIGHT, self.TARGET, None))

    def test_wrong_minute_is_not_due(self):
        friday_2201 = datetime(2026, 8, 7, 22, 1)
        self.assertFalse(is_due(friday_2201, self.TARGET, (4,)))


class TestMorningGreeting(unittest.TestCase):
    def test_uses_morning_call_session_without_timeout_override(self):
        agent = FakeAgent("早安呀！")
        messages = make_messages(agent, FakeSongChooser("https://youtu.be/abc123"))

        greeting = messages.morning_greeting(MONDAY_MORNING, "7:30")

        call = agent.calls[-1]
        self.assertEqual(call["channel_id"], "morning-call")
        self.assertNotIn("timeout", call)
        self.assertIn("星期一", call["question"])
        # 天氣播報：指定工具、並要求取不到時降級略過（實測全台總覽約 8 秒，無需放寬逾時）
        self.assertIn("tw_weather", call["question"])
        self.assertIn("取不到就略過", call["question"])
        self.assertIn("早安呀！", greeting)
        self.assertIn("(https://youtu.be/abc123)", greeting)

    def test_api_failure_still_builds_message(self):
        # 早安維持原行為：AI 故障時仍發出訊息（含降級文字），不靜默跳過
        messages = make_messages(
            FakeAgent(API_FAIL_MESSAGE), FakeSongChooser("歌單服務暫時連不上線")
        )

        greeting = messages.morning_greeting(MONDAY_MORNING, "7:30")

        self.assertIn(API_FAIL_MESSAGE, greeting)


class TestMorningHolidayEasterEgg(unittest.TestCase):
    def _question_on(self, morning):
        agent = FakeAgent("早安呀！")
        messages = make_messages(agent, FakeSongChooser("https://youtu.be/abc123"))
        messages.morning_greeting(morning, "7:30")
        return agent.calls[-1]["question"]

    def test_plain_day_has_no_easter_egg_line(self):
        # 2026-08-03 非節日：Prompt 維持原樣，不出現彩蛋指示
        question = self._question_on(MONDAY_MORNING)
        self.assertNotIn("節日彩蛋", question)
        self.assertNotIn("補假日", question)

    def test_festival_adds_easter_egg_line(self):
        question = self._question_on(datetime(2026, 9, 25, 7, 30))
        self.assertIn("「中秋節」", question)
        self.assertIn("節日彩蛋", question)

    def test_lunar_festival_adds_easter_egg_line(self):
        question = self._question_on(datetime(2026, 8, 19, 7, 30))
        self.assertIn("「七夕情人節」", question)

    def test_makeup_day_adds_travel_care_line(self):
        question = self._question_on(datetime(2026, 2, 27, 7, 30))
        self.assertIn("「和平紀念日」連假的補假日", question)
        self.assertIn("塞車", question)

    def test_lookup_failure_degrades_to_plain_greeting(self):
        # 節日查詢炸掉時要吞下例外、照常打招呼，不能拖垮整則早安
        agent = FakeAgent("早安呀！")
        messages = make_messages(agent, FakeSongChooser("https://youtu.be/abc123"))

        with mock.patch(
            "tm_bot.services.scheduler.jobs.get_holiday_info", side_effect=RuntimeError("boom")
        ):
            greeting = messages.morning_greeting(datetime(2026, 9, 25, 7, 30), "7:30")

        self.assertIn("早安呀！", greeting)
        self.assertNotIn("節日彩蛋", agent.calls[-1]["question"])


class TestCatchUpDelay(unittest.TestCase):
    """開機補發的時間規則（不含「發過了沒」的判斷，那是紀錄庫的事）。"""

    TARGET = datetime.strptime("7:30", "%H:%M")

    def test_returns_none_before_target_time(self):
        # 今天還沒到七點半：交給正常排程，不是補發的事
        self.assertIsNone(catch_up_delay(datetime(2026, 8, 17, 6, 0), self.TARGET, None, 3))

    def test_returns_delay_within_window(self):
        delay = catch_up_delay(datetime(2026, 8, 17, 9, 15), self.TARGET, None, 3)
        self.assertEqual(delay, timedelta(hours=1, minutes=45))

    def test_returns_none_after_window(self):
        # 遲超過三小時（10:30 之後）就不補了，這時候才說早安反而突兀
        self.assertIsNone(catch_up_delay(datetime(2026, 8, 17, 11, 0), self.TARGET, None, 3))

    def test_boundary_of_window_still_catches_up(self):
        self.assertIsNotNone(catch_up_delay(datetime(2026, 8, 17, 10, 30), self.TARGET, None, 3))

    def test_zero_hours_disables_catch_up(self):
        self.assertIsNone(catch_up_delay(datetime(2026, 8, 17, 8, 0), self.TARGET, None, 0))

    def test_weekday_filter_applies(self):
        friday_target = datetime.strptime("22:00", "%H:%M")
        # 2026-08-08 為星期六：即使時間在窗內，非排定星期也不補
        self.assertIsNone(catch_up_delay(datetime(2026, 8, 8, 23, 0), friday_target, (4,), 2))
        self.assertIsNotNone(catch_up_delay(datetime(2026, 8, 7, 23, 0), friday_target, (4,), 2))

    def test_catch_up_never_crosses_midnight(self):
        # 週五 22:00 的推播，到了週六凌晨就不該再補（今天的 target 落在未來）
        friday_target = datetime.strptime("22:00", "%H:%M")
        self.assertIsNone(catch_up_delay(datetime(2026, 8, 8, 0, 30), friday_target, (4,), 2))


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content):
        self.sent.append(content)


class FakeClient:
    def __init__(self, channel=None):
        self.channel = channel

    async def wait_until_ready(self):
        return

    def get_channel(self, _channel_id):
        return self.channel


class FakeRuns:
    """記錄呼叫順序的假紀錄庫，用來驗證認領／釋放／標記的時機。"""

    def __init__(self, allow=True, enabled=True):
        self.allow = allow
        self.enabled = enabled
        self.calls = []

    def claim(self, job_label, day, fail_open=True):
        self.calls.append(("claim", job_label, day, fail_open))
        return self.allow

    def release(self, job_label, day):
        self.calls.append(("release", job_label, day))

    def mark_sent(self, job_label, day, chars):
        self.calls.append(("mark_sent", job_label, day, chars))

    def names(self):
        return [call[0] for call in self.calls]


def make_scheduler(runs, channel=None):
    return Scheduler(FakeClient(channel), make_settings(), runs=runs)


def make_job(build, **overrides):
    values = {
        "label": "早安",
        "time_str": "7:30",
        "channel_key": "chitchat_channel_id",
        "build": build,
    }
    values.update(overrides)
    return ScheduledJob(**values)


class TestDispatch(unittest.IsolatedAsyncioTestCase):
    """發送流程的可靠度：認領 → 產生內容 → 發送 → 記錄。"""

    async def test_successful_send_marks_sent(self):
        runs = FakeRuns()
        channel = FakeChannel()
        scheduler = make_scheduler(runs, channel)

        sent = await scheduler._dispatch(make_job(lambda now, t: "早安啊"), MONDAY_MORNING, "7:30")

        self.assertTrue(sent)
        self.assertEqual(channel.sent, ["早安啊"])
        self.assertEqual(runs.names(), ["claim", "mark_sent"])
        self.assertEqual(runs.calls[-1], ("mark_sent", "早安", MONDAY_MORNING.date(), 3))

    async def test_refused_claim_sends_nothing(self):
        # 今天已經發過（或另一個實例正在處理）：連內容都不該去產
        runs = FakeRuns(allow=False)
        channel = FakeChannel()
        built = []

        def build(now, time_str):
            built.append(now)
            return "早安啊"

        sent = await make_scheduler(runs, channel)._dispatch(
            make_job(build), MONDAY_MORNING, "7:30"
        )

        self.assertFalse(sent)
        self.assertEqual(channel.sent, [])
        self.assertEqual(built, [])
        self.assertEqual(runs.names(), ["claim"])

    async def test_silent_skip_releases_claim(self):
        # 內容產不出來（AI 兩次都失敗）→ 認領要還回去，稍後補發才有機會重試
        runs = FakeRuns()
        channel = FakeChannel()

        sent = await make_scheduler(runs, channel)._dispatch(
            make_job(lambda now, t: None), MONDAY_MORNING, "7:30"
        )

        self.assertFalse(sent)
        self.assertEqual(channel.sent, [])
        self.assertEqual(runs.names(), ["claim", "release"])

    async def test_missing_channel_releases_claim(self):
        runs = FakeRuns()

        sent = await make_scheduler(runs, channel=None)._dispatch(
            make_job(lambda now, t: "早安啊"), MONDAY_MORNING, "7:30"
        )

        self.assertFalse(sent)
        self.assertEqual(runs.names(), ["claim", "release"])

    async def test_exception_releases_claim_and_propagates(self):
        runs = FakeRuns()

        def build(now, time_str):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            await make_scheduler(runs, FakeChannel())._dispatch(
                make_job(build), MONDAY_MORNING, "7:30"
            )

        self.assertEqual(runs.names(), ["claim", "release"])


class TestCatchUp(unittest.IsolatedAsyncioTestCase):
    TARGET = datetime.strptime("7:30", "%H:%M")

    async def test_disabled_storage_never_catches_up(self):
        # 沒有紀錄就無從判斷發過沒，硬補等於每次重啟都洗版
        runs = FakeRuns(enabled=False)
        channel = FakeChannel()

        await make_scheduler(runs, channel)._catch_up(
            make_job(lambda now, t: "早安啊"), self.TARGET
        )

        self.assertEqual(runs.calls, [])
        self.assertEqual(channel.sent, [])

    async def test_catch_up_claims_fail_closed(self):
        runs = FakeRuns()
        channel = FakeChannel()
        scheduler = make_scheduler(runs, channel)
        job = make_job(lambda now, t: "補發的早安")

        with mock.patch(
            "tm_bot.services.scheduler.runner.datetime", wraps=datetime
        ) as fake_datetime:
            fake_datetime.now.return_value = datetime(2026, 8, 17, 9, 15)
            await scheduler._catch_up(job, self.TARGET)

        self.assertEqual(channel.sent, ["補發的早安"])
        # fail_open=False：Mongo 剛好不通就別補，寧可漏發也不要重複發
        self.assertEqual(runs.calls[0], ("claim", "早安", datetime(2026, 8, 17).date(), False))

    async def test_catch_up_reports_the_real_current_time(self):
        # 09:15 補發卻宣稱「現在時間是 7:30」會很奇怪，要如實告知內容產生器
        runs = FakeRuns()
        seen = []
        scheduler = make_scheduler(runs, FakeChannel())

        def build(now, time_str):
            seen.append(time_str)
            return "補發的早安"

        with mock.patch(
            "tm_bot.services.scheduler.runner.datetime", wraps=datetime
        ) as fake_datetime:
            fake_datetime.now.return_value = datetime(2026, 8, 17, 9, 5)
            await scheduler._catch_up(make_job(build), self.TARGET)

        self.assertEqual(seen, ["9:05"])


if __name__ == "__main__":
    unittest.main()
