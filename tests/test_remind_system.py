import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

# remind_system 內部以 scripts/ 為根匯入（config_utils、plugins.*），需先加入 sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "tm_discord_bot" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugins import ai_agent_client  # noqa: E402
from plugins.ai_agent_client import API_FAIL_MESSAGE  # noqa: E402
from plugins.remind_system import (  # noqa: E402
    AI_RETRY_DELAY,
    GAME_DEALS_SENTINEL,
    GAME_DEALS_TIMEOUT,
    NIGHT_TRENDS_TIMEOUT,
    RemindSystem,
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


def make_remind_system(ai_agent, yt_song_chooser=None):
    # 繞過 Singleton 的 __new__ 與需要 .env/config.ini 的 __init__，只掛測試所需屬性
    rs = object.__new__(RemindSystem)
    rs.ai_agent = ai_agent
    rs.yt_song_chooser = yt_song_chooser
    return rs


class TestNightTrends(unittest.TestCase):
    def test_success_uses_dedicated_session_and_timeout(self):
        agent = FakeAgent("今晚話題來囉！")
        rs = make_remind_system(agent)

        result = rs._RemindSystem__get_night_trends(MONDAY_NIGHT, "22:00")

        self.assertEqual(result, "今晚話題來囉！")
        # 一次就成功時不會多打第二次
        self.assertEqual(len(agent.calls), 1)
        call = agent.calls[-1]
        self.assertEqual(call["user_id"], "night-trends")
        self.assertEqual(call["channel_id"], "night-trends")
        self.assertEqual(call["timeout"], NIGHT_TRENDS_TIMEOUT)

    def test_prompt_contains_tool_and_filter_rules(self):
        agent = FakeAgent("今晚話題來囉！")
        rs = make_remind_system(agent)

        rs._RemindSystem__get_night_trends(MONDAY_NIGHT, "22:00")

        question = agent.calls[-1]["question"]
        self.assertIn("tw_trends_news", question)
        self.assertIn("排除政治", question)
        self.assertIn("悲劇社會案件", question)
        self.assertIn("星期一", question)

    def test_first_failure_retries_once_and_posts_retry_answer(self):
        agent = FakeAgent(API_FAIL_MESSAGE, "重試後拿到的話題！")
        rs = make_remind_system(agent)

        with mock.patch("plugins.remind_system.time.sleep") as fake_sleep:
            result = rs._RemindSystem__get_night_trends(MONDAY_NIGHT, "22:00")

        self.assertEqual(result, "重試後拿到的話題！")
        self.assertEqual(len(agent.calls), 2)
        # 重試前有留緩衝間隔，讓 n8n／LLM 喘息
        fake_sleep.assert_called_once_with(AI_RETRY_DELAY)

    def test_api_failure_after_retry_returns_none_for_silent_skip(self):
        agent = FakeAgent(API_FAIL_MESSAGE)

        with mock.patch("plugins.remind_system.time.sleep") as fake_sleep:
            result = make_remind_system(agent)._RemindSystem__get_night_trends(
                MONDAY_NIGHT, "22:00"
            )

        self.assertIsNone(result)
        # 只重試一次（共打兩次）就放棄，避免無限重打
        self.assertEqual(len(agent.calls), 2)
        fake_sleep.assert_called_once()


class TestGameDeals(unittest.TestCase):
    def test_success_uses_dedicated_session_and_timeout(self):
        agent = FakeAgent("本週遊戲情報來囉！")
        rs = make_remind_system(agent)

        result = rs._RemindSystem__get_game_deals(FRIDAY_NIGHT, "22:00")

        self.assertEqual(result, "本週遊戲情報來囉！")
        self.assertEqual(len(agent.calls), 1)
        call = agent.calls[-1]
        self.assertEqual(call["user_id"], "game-deals")
        self.assertEqual(call["channel_id"], "game-deals")
        self.assertEqual(call["timeout"], GAME_DEALS_TIMEOUT)

    def test_prompt_contains_tool_and_selection_rules(self):
        agent = FakeAgent("ok")
        rs = make_remind_system(agent)

        rs._RemindSystem__get_game_deals(FRIDAY_NIGHT, "22:00")

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
        rs = make_remind_system(FakeAgent(GAME_DEALS_SENTINEL))

        self.assertIsNone(rs._RemindSystem__get_game_deals(FRIDAY_NIGHT, "22:00"))

    def test_api_failure_after_retry_returns_none(self):
        agent = FakeAgent(API_FAIL_MESSAGE)

        with mock.patch("plugins.remind_system.time.sleep") as fake_sleep:
            result = make_remind_system(agent)._RemindSystem__get_game_deals(
                FRIDAY_NIGHT, "22:00"
            )

        self.assertIsNone(result)
        self.assertEqual(len(agent.calls), 2)
        fake_sleep.assert_called_once_with(AI_RETRY_DELAY)


class TestWeekdayFilter(unittest.TestCase):
    TARGET = datetime.strptime("22:00", "%H:%M")

    def test_friday_2200_is_due(self):
        # 2026-08-07 為星期五（weekday=4）
        self.assertTrue(RemindSystem._is_due(FRIDAY_NIGHT, self.TARGET, [4]))

    def test_other_weekday_is_not_due(self):
        # 2026-08-03 為星期一：時間相同但星期不符
        self.assertFalse(RemindSystem._is_due(MONDAY_NIGHT, self.TARGET, [4]))

    def test_none_weekdays_means_daily(self):
        self.assertTrue(RemindSystem._is_due(MONDAY_NIGHT, self.TARGET, None))

    def test_wrong_minute_is_not_due(self):
        friday_2201 = datetime(2026, 8, 7, 22, 1)
        self.assertFalse(RemindSystem._is_due(friday_2201, self.TARGET, [4]))


class TestMorningGreetingUnchanged(unittest.TestCase):
    def test_uses_morning_call_session_without_timeout_override(self):
        agent = FakeAgent("早安呀！")
        rs = make_remind_system(agent, FakeSongChooser("https://youtu.be/abc123"))

        greeting = rs._RemindSystem__get_morning_greeting(MONDAY_MORNING, "7:30")

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
        rs = make_remind_system(
            FakeAgent(API_FAIL_MESSAGE), FakeSongChooser("歌單服務暫時連不上線")
        )

        greeting = rs._RemindSystem__get_morning_greeting(MONDAY_MORNING, "7:30")

        self.assertIn(API_FAIL_MESSAGE, greeting)


class TestMorningHolidayEasterEgg(unittest.TestCase):
    def _question_on(self, morning):
        agent = FakeAgent("早安呀！")
        rs = make_remind_system(agent, FakeSongChooser("https://youtu.be/abc123"))
        rs._RemindSystem__get_morning_greeting(morning, "7:30")
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
        rs = make_remind_system(agent, FakeSongChooser("https://youtu.be/abc123"))

        with mock.patch(
            "plugins.remind_system.get_holiday_info", side_effect=RuntimeError("boom")
        ):
            greeting = rs._RemindSystem__get_morning_greeting(
                datetime(2026, 9, 25, 7, 30), "7:30"
            )

        self.assertIn("早安呀！", greeting)
        self.assertNotIn("節日彩蛋", agent.calls[-1]["question"])


class TestAskTimeoutOverride(unittest.TestCase):
    def _make_client(self):
        with mock.patch.dict(
            "os.environ",
            {
                "N8N_AGENT_WEBHOOK_URL": "http://localhost:5678/webhook/test",
                "N8N_WEBHOOK_SECRET": "test-secret",
            },
        ):
            return ai_agent_client.AIAgentClient()

    def _ask_and_capture_timeout(self, client, **kwargs):
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"reply": "ok"}'

        def fake_urlopen(req, timeout=None):
            captured["timeout"] = timeout
            return FakeResp()

        with mock.patch.object(
            ai_agent_client.urllib.request, "urlopen", fake_urlopen
        ):
            client.ask(question="hi", **kwargs)
        return captured["timeout"]

    def test_default_timeout_when_not_specified(self):
        client = self._make_client()
        self.assertEqual(self._ask_and_capture_timeout(client), client.timeout)

    def test_caller_can_override_timeout(self):
        client = self._make_client()
        self.assertEqual(self._ask_and_capture_timeout(client, timeout=120), 120)


if __name__ == "__main__":
    unittest.main()
