import unittest
from unittest import mock

from tm_bot.clients.http import WebhookError
from tm_bot.clients.maps_review import MapsReviewClient
from tm_bot.ui.maps import MAPS_ERROR_MESSAGES, build_maps_embed, build_maps_error_message

URL = "https://maps.app.goo.gl/AbCdEf123"

PLACE = {
    "name": "鼎泰豐 信義店",
    "address": "台北市大安區信義路二段194號",
    "maps_uri": "https://maps.google.com/?cid=123",
    "rating": 4.3,
    "rating_count": 1847,
}
REVIEW = {
    "verdict": "小籠包穩定好吃，但假日要排隊。",
    "positive": ["小籠包皮薄湯多", "服務細心"],
    "negative": ["假日等超過一小時", "價格偏高"],
}
SOURCES = [{"title": "鼎泰豐 信義店", "uri": "https://maps.google.com/?cid=123"}]


def make_client():
    return MapsReviewClient("http://n8n/webhook/maps-review", "secret", 120)


def call_with(body):
    with mock.patch("tm_bot.clients.maps_review.post_json", return_value=body):
        return make_client().review(URL)


def ok_body(**overrides):
    body = {"ok": True, "place": dict(PLACE), "review": dict(REVIEW), "sources": list(SOURCES)}
    body.update(overrides)
    return body


class TestMapsReviewClient(unittest.TestCase):
    def test_sends_url_with_secret_and_timeout(self):
        with mock.patch(
            "tm_bot.clients.maps_review.post_json", return_value=ok_body()
        ) as post_json:
            make_client().review(URL)

        args = post_json.call_args.args
        self.assertEqual(args[0], "http://n8n/webhook/maps-review")
        self.assertEqual(args[1], {"url": URL})
        self.assertEqual(args[2], "secret")
        self.assertEqual(args[3], 120)

    def test_valid_body_passes_through(self):
        self.assertEqual(call_with(ok_body())["place"]["name"], "鼎泰豐 信義店")

    def test_webhook_failure_becomes_upstream_error(self):
        with mock.patch(
            "tm_bot.clients.maps_review.post_json", side_effect=WebhookError("timeout")
        ):
            result = make_client().review(URL)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "UPSTREAM_ERROR")

    def test_n8n_error_code_is_preserved(self):
        result = call_with({"ok": False, "error_code": "URL_UNRESOLVED"})
        self.assertEqual(result["error_code"], "URL_UNRESOLVED")

    def test_failure_without_error_code_falls_back(self):
        self.assertEqual(call_with({"ok": False})["error_code"], "UPSTREAM_ERROR")

    def test_missing_place_name_is_rejected(self):
        self.assertEqual(
            call_with(ok_body(place={"address": "某處"}))["error_code"], "SUMMARY_FAILED"
        )

    def test_missing_review_is_rejected(self):
        self.assertEqual(call_with(ok_body(review=None))["error_code"], "SUMMARY_FAILED")

    def test_missing_sources_is_rejected(self):
        # Google 要求 grounded 內容必須附來源，沒有來源就不能貼摘要
        self.assertEqual(call_with(ok_body(sources=[]))["error_code"], "MISSING_SOURCES")

    def test_sources_without_uri_are_rejected(self):
        body = ok_body(sources=[{"title": "只有標題"}])
        self.assertEqual(call_with(body)["error_code"], "MISSING_SOURCES")


class TestMapsErrorMessage(unittest.TestCase):
    def test_known_error_code(self):
        message = build_maps_error_message({"error_code": "NO_REVIEW_DATA"})
        self.assertEqual(message, MAPS_ERROR_MESSAGES["NO_REVIEW_DATA"])

    def test_unknown_error_code_falls_back(self):
        message = build_maps_error_message({"error_code": "WHAT_IS_THIS"})
        self.assertEqual(message, MAPS_ERROR_MESSAGES["UPSTREAM_ERROR"])


class TestMapsEmbed(unittest.TestCase):
    def setUp(self):
        self.embed = build_maps_embed(ok_body())

    def test_title_and_link(self):
        self.assertEqual(self.embed.title, "鼎泰豐 信義店")
        self.assertEqual(self.embed.url, "https://maps.google.com/?cid=123")

    def test_description_has_verdict_and_both_sides(self):
        description = self.embed.description
        self.assertIn("小籠包穩定好吃", description)
        self.assertIn("👍", description)
        self.assertIn("• 小籠包皮薄湯多", description)
        self.assertIn("👎", description)
        self.assertIn("• 假日等超過一小時", description)

    def test_sources_field_is_present_with_bracketed_links(self):
        # 來源是規定而非裝飾；角括號抑制 Discord 預覽卡片
        field = next(f for f in self.embed.fields if "來源" in f.name)
        self.assertIn("(<https://maps.google.com/?cid=123>)", field.value)

    def test_footer_has_rating_and_attribution(self):
        self.assertIn("⭐ 4.3", self.embed.footer.text)
        self.assertIn("1,847 則評論", self.embed.footer.text)
        self.assertIn("Google Maps", self.embed.footer.text)

    def test_optional_fields_can_be_absent(self):
        embed = build_maps_embed({"place": {"name": "某店"}, "review": {}, "sources": []})
        self.assertEqual(embed.title, "某店")
        self.assertIsNone(embed.url)
        self.assertEqual(embed.description, "")
        self.assertIn("Google Maps", embed.footer.text)

    def test_caveat_is_rendered_as_small_text(self):
        review = dict(REVIEW, caveat="評論偏少，僅供參考")
        embed = build_maps_embed(ok_body(review=review))
        self.assertIn("-# ⚠️ 評論偏少，僅供參考", embed.description)

    def test_sources_are_capped(self):
        many = [{"title": f"來源{i}", "uri": f"https://example.com/{i}"} for i in range(12)]
        embed = build_maps_embed(ok_body(sources=many))
        field = next(f for f in embed.fields if "來源" in f.name)
        self.assertEqual(len(field.value.splitlines()), 5)

    def test_garbage_rating_count_does_not_crash(self):
        place = dict(PLACE, rating_count="很多")
        embed = build_maps_embed(ok_body(place=place))
        self.assertIn("Google Maps", embed.footer.text)


if __name__ == "__main__":
    unittest.main()
