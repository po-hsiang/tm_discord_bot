import unittest
from unittest import mock

import requests

from tm_bot.clients.http import WEBHOOK_SECRET_HEADER, WebhookError, post_json

URL = "http://localhost:5678/webhook/test"


class FakeResponse:
    def __init__(self, body=None, error=None, json_error=False):
        self._body = body
        self._error = error
        self._json_error = json_error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        if self._json_error:
            raise ValueError("not json")
        return self._body


def call(response):
    with mock.patch("tm_bot.clients.http.requests.post", return_value=response) as post:
        result = post_json(URL, {"text": "hi"}, "secret", 60)
    return result, post


class TestPostJson(unittest.TestCase):
    def test_returns_parsed_body(self):
        result, _ = call(FakeResponse({"reply": "ok"}))
        self.assertEqual(result, {"reply": "ok"})

    def test_sends_secret_header_and_timeout(self):
        _, post = call(FakeResponse({"reply": "ok"}))
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"][WEBHOOK_SECRET_HEADER], "secret")
        self.assertEqual(kwargs["timeout"], 60)
        self.assertEqual(kwargs["json"], {"text": "hi"})

    def test_http_error_becomes_webhook_error(self):
        with self.assertRaises(WebhookError):
            call(FakeResponse(error=requests.HTTPError("500 Server Error")))

    def test_connection_failure_becomes_webhook_error(self):
        with (
            mock.patch(
                "tm_bot.clients.http.requests.post",
                side_effect=requests.ConnectionError("refused"),
            ),
            self.assertRaises(WebhookError),
        ):
            post_json(URL, {}, "secret", 60)

    def test_non_json_response_becomes_webhook_error(self):
        with self.assertRaises(WebhookError):
            call(FakeResponse(json_error=True))

    def test_non_object_json_becomes_webhook_error(self):
        # 回傳陣列或字串時，呼叫端的 body.get() 會炸掉，在此先擋下
        with self.assertRaises(WebhookError):
            call(FakeResponse([1, 2, 3]))


if __name__ == "__main__":
    unittest.main()
