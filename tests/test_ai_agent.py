import unittest
from unittest import mock

from tm_bot.clients.ai_agent import API_FAIL_MESSAGE, EMPTY_QUESTION_MESSAGE, AIAgentClient
from tm_bot.clients.http import WebhookError


def make_client():
    # 設定改由建構子注入，測試不再需要動 os.environ
    return AIAgentClient("http://localhost:5678/webhook/test", "test-secret")


class TestAskTimeoutOverride(unittest.TestCase):
    def _ask_and_capture_timeout(self, client, **kwargs):
        captured = {}

        def fake_post_json(url, payload, secret, timeout):
            captured["timeout"] = timeout
            return {"reply": "ok"}

        with mock.patch("tm_bot.clients.ai_agent.post_json", fake_post_json):
            client.ask(question="hi", **kwargs)
        return captured["timeout"]

    def test_default_timeout_when_not_specified(self):
        client = make_client()
        self.assertEqual(self._ask_and_capture_timeout(client), client.timeout)

    def test_caller_can_override_timeout(self):
        # 晚間話題／遊戲情報要等 n8n 端工具抓資料，逾時需放寬
        client = make_client()
        self.assertEqual(self._ask_and_capture_timeout(client, timeout=120), 120)


class TestAskDegradation(unittest.TestCase):
    def test_empty_question_short_circuits_without_http_call(self):
        with mock.patch("tm_bot.clients.ai_agent.post_json") as post:
            reply = make_client().ask(question="   ")

        self.assertEqual(reply, EMPTY_QUESTION_MESSAGE)
        post.assert_not_called()

    def test_image_only_message_still_calls_agent(self):
        # 純圖片／貼圖訊息沒有文字，仍要送給 AI 看
        with mock.patch("tm_bot.clients.ai_agent.post_json", return_value={"reply": "看到圖了"}):
            reply = make_client().ask(question="", images=[{"url": "http://x/1.png"}])

        self.assertEqual(reply, "看到圖了")

    def test_webhook_error_returns_fail_message(self):
        with mock.patch("tm_bot.clients.ai_agent.post_json", side_effect=WebhookError("timeout")):
            self.assertEqual(make_client().ask(question="hi"), API_FAIL_MESSAGE)

    def test_blank_reply_returns_fail_message(self):
        with mock.patch("tm_bot.clients.ai_agent.post_json", return_value={"reply": "  "}):
            self.assertEqual(make_client().ask(question="hi"), API_FAIL_MESSAGE)


if __name__ == "__main__":
    unittest.main()
