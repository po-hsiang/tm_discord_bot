import unittest
from unittest import mock

from tm_bot.clients.ai_agent import EMPTY_QUESTION_MESSAGE, AIAgentClient


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"reply": "ok"}'


class TestAskTimeoutOverride(unittest.TestCase):
    def _make_client(self):
        # 設定改由建構子注入，測試不再需要動 os.environ
        return AIAgentClient("http://localhost:5678/webhook/test", "test-secret")

    def _ask_and_capture_timeout(self, client, **kwargs):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["timeout"] = timeout
            return FakeResponse()

        with mock.patch("tm_bot.clients.ai_agent.urllib.request.urlopen", fake_urlopen):
            client.ask(question="hi", **kwargs)
        return captured["timeout"]

    def test_default_timeout_when_not_specified(self):
        client = self._make_client()
        self.assertEqual(self._ask_and_capture_timeout(client), client.timeout)

    def test_caller_can_override_timeout(self):
        client = self._make_client()
        self.assertEqual(self._ask_and_capture_timeout(client, timeout=120), 120)


class TestEmptyQuestion(unittest.TestCase):
    def test_no_text_no_attachment_short_circuits_without_http_call(self):
        client = AIAgentClient("http://localhost:5678/webhook/test", "test-secret")

        with mock.patch("tm_bot.clients.ai_agent.urllib.request.urlopen") as urlopen:
            reply = client.ask(question="   ")

        self.assertEqual(reply, EMPTY_QUESTION_MESSAGE)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
