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
from plugins.remind_system import NIGHT_TRENDS_TIMEOUT, RemindSystem  # noqa: E402

MONDAY_NIGHT = datetime(2026, 8, 3, 22, 0)
MONDAY_MORNING = datetime(2026, 8, 3, 7, 30)


class FakeAgent:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def ask(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.reply


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

    def test_api_failure_returns_none_for_silent_skip(self):
        rs = make_remind_system(FakeAgent(API_FAIL_MESSAGE))

        self.assertIsNone(rs._RemindSystem__get_night_trends(MONDAY_NIGHT, "22:00"))


class TestMorningGreetingUnchanged(unittest.TestCase):
    def test_uses_morning_call_session_without_timeout_override(self):
        agent = FakeAgent("早安呀！")
        rs = make_remind_system(agent, FakeSongChooser("https://youtu.be/abc123"))

        greeting = rs._RemindSystem__get_morning_greeting(MONDAY_MORNING, "7:30")

        call = agent.calls[-1]
        self.assertEqual(call["channel_id"], "morning-call")
        self.assertNotIn("timeout", call)
        self.assertIn("星期一", call["question"])
        self.assertIn("早安呀！", greeting)
        self.assertIn("(https://youtu.be/abc123)", greeting)

    def test_api_failure_still_builds_message(self):
        # 早安維持原行為：AI 故障時仍發出訊息（含降級文字），不靜默跳過
        rs = make_remind_system(
            FakeAgent(API_FAIL_MESSAGE), FakeSongChooser("歌單服務暫時連不上線")
        )

        greeting = rs._RemindSystem__get_morning_greeting(MONDAY_MORNING, "7:30")

        self.assertIn(API_FAIL_MESSAGE, greeting)


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
