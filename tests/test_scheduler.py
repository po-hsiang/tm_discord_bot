import unittest
from datetime import datetime
from unittest import mock

from tm_bot.clients.ai_agent import API_FAIL_MESSAGE
from tm_bot.services.scheduler.jobs import (
    AI_RETRY_DELAY,
    GAME_DEALS_TIMEOUT,
    NIGHT_TRENDS_TIMEOUT,
    ScheduledMessages,
    build_jobs,
)
from tm_bot.services.scheduler.prompts import GAME_DEALS_SENTINEL
from tm_bot.services.scheduler.runner import is_due

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

    def test_night_trends_job(self):
        job = self.jobs["晚間話題"]
        self.assertEqual(job.time_str, "19:30")
        self.assertEqual(job.channel_key, "chitchat_channel_id")
        self.assertIsNone(job.weekdays)

    def test_game_deals_job_is_friday_only(self):
        job = self.jobs["遊戲情報"]
        self.assertEqual(job.time_str, "22:00")
        self.assertEqual(job.channel_key, "game_deals_channel_id")
        self.assertEqual(job.weekdays, (4,))  # 只在星期五


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
        self.assertIn("悲劇社會案件", question)
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


if __name__ == "__main__":
    unittest.main()
