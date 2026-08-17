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
# 真實資料的來源清單長這樣：一筆店家頁面 ＋ 一筆評論。
# 只有後者算評論樣本，前者不是任何人的評論
PLACE_SOURCE = {
    "title": "鼎泰豐 信義店 - Google Maps",
    "uri": "https://maps.google.com/maps?cid=123",
}
REVIEW_SOURCE = {
    "title": "Review of 鼎泰豐 信義店 - Google Maps",
    "uri": "https://www.google.com/maps/reviews/data=!4m6!14m5!1m4",
}
SOURCES = [PLACE_SOURCE, REVIEW_SOURCE]


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


def many_sources(count):
    return [{"title": f"來源{i}", "uri": f"https://example.com/{i}"} for i in range(count)]


def review_sources(count):
    return [
        {"title": f"Review {i}", "uri": f"https://www.google.com/maps/reviews/data=!{i}"}
        for i in range(count)
    ]


class TestMapsEmbed(unittest.TestCase):
    def setUp(self):
        self.embed = build_maps_embed(ok_body())

    def test_title_and_link(self):
        self.assertEqual(self.embed.title, "鼎泰豐 信義店")
        self.assertEqual(self.embed.url, "https://maps.google.com/?cid=123")

    def test_rating_leads_the_description(self):
        # 評分是唯一可靠的彙總信號，必須是第一眼看到的東西
        first_line = self.embed.description.splitlines()[0]
        self.assertIn("⭐ **4.3**", first_line)
        self.assertIn("1,847 則評論", first_line)

    def test_description_has_verdict_and_both_sides(self):
        description = self.embed.description
        self.assertIn("小籠包穩定好吃", description)
        self.assertIn("👍", description)
        self.assertIn("• 小籠包皮薄湯多", description)
        self.assertIn("👎", description)
        self.assertIn("• 假日等超過一小時", description)

    def test_footer_is_attribution_only(self):
        # 評分已在描述開頭，頁尾不再重複同一組數字
        self.assertEqual(self.embed.footer.text, "資料來源 Google Maps")

    def test_sources_field_is_present_with_bracketed_links(self):
        # 來源是規定而非裝飾；角括號抑制 Discord 預覽卡片
        field = next(f for f in self.embed.fields if "來源" in f.name)
        self.assertIn("(<https://maps.google.com/maps?cid=123>)", field.value)
        self.assertEqual(len(field.value.splitlines()), 2)

    def test_sources_are_capped(self):
        embed = build_maps_embed(ok_body(sources=many_sources(12)))
        field = next(f for f in embed.fields if "來源" in f.name)
        self.assertEqual(len(field.value.splitlines()), 5)

    def test_optional_fields_can_be_absent(self):
        embed = build_maps_embed({"place": {"name": "某店"}, "review": {}, "sources": []})
        self.assertEqual(embed.title, "某店")
        self.assertIsNone(embed.url)
        self.assertIn("👎", embed.description)  # 負評區塊仍在
        self.assertEqual(embed.footer.text, "資料來源 Google Maps")

    def test_garbage_rating_count_does_not_crash(self):
        embed = build_maps_embed(ok_body(place=dict(PLACE, rating_count="很多")))
        self.assertIn("⭐ **4.3**", embed.description)


class TestNegativeSectionAlwaysShown(unittest.TestCase):
    """實測發現 negative 幾乎永遠是空的（只撈到一則評論），
    整段消失會讓人以為壞掉，宣稱「這家店沒負評」又是過度推論。"""

    def test_empty_negative_says_what_is_actually_true(self):
        embed = build_maps_embed(ok_body(review=dict(REVIEW, negative=[])))
        self.assertIn("👎 **負評**", embed.description)
        self.assertIn("這次摘到的評論裡沒有出現負評", embed.description)

    def test_missing_negative_key_behaves_the_same(self):
        review = {"verdict": "還不錯", "positive": ["好吃"]}
        self.assertIn("沒有出現負評", build_maps_embed(ok_body(review=review)).description)


class TestProvenanceLine(unittest.TestCase):
    """樣本大小的交代由程式計算——模型曾經只拿到一則評論卻回空的 caveat。"""

    def test_thin_sample_counts_reviews_not_sources(self):
        # 兩筆來源其實是「一筆店家頁面 + 一則評論」，說 2 就是多報
        description = build_maps_embed(ok_body()).description
        self.assertIn("以上摘自 Google Maps 提供的 1 則評論", description)
        self.assertIn("不代表 1,847 則評論的整體風向", description)
        # 不是小字：樣本大小對判讀的影響太大，不該被當附註
        self.assertNotIn("-# ⚠️ 以上摘自", description)

    def test_warning_omits_comparison_when_rating_count_unknown(self):
        place = {k: v for k, v in PLACE.items() if k != "rating_count"}
        description = build_maps_embed(ok_body(place=place)).description
        self.assertIn("1 則評論，樣本偏少僅供參考", description)

    def test_no_identifiable_review_source_avoids_inventing_a_number(self):
        description = build_maps_embed(ok_body(sources=[PLACE_SOURCE])).description
        self.assertIn("這次沒有取得可對照的評論來源", description)

    def test_enough_reviews_drops_the_warning(self):
        description = build_maps_embed(ok_body(sources=review_sources(3))).description
        self.assertNotIn("以上摘自", description)
        self.assertNotIn("沒有取得可對照", description)

    def test_model_caveat_shown_only_when_sample_is_not_thin(self):
        # 樣本足夠時，模型的 caveat 講的才是別的事（例如評論互相矛盾）
        review = dict(REVIEW, caveat="評論內容互相矛盾")
        body = ok_body(review=review, sources=review_sources(3))
        self.assertIn("-# ⚠️ 評論內容互相矛盾", build_maps_embed(body).description)

    def test_model_caveat_suppressed_when_thin_warning_already_fired(self):
        # 兩條都講會變成重複警告，以程式算的那條為準
        review = dict(REVIEW, caveat="撈到的評論偏少")
        description = build_maps_embed(ok_body(review=review)).description
        self.assertIn("以上摘自", description)
        self.assertNotIn("撈到的評論偏少", description)

    def test_sources_without_uri_do_not_count_as_sample(self):
        body = ok_body(sources=[*SOURCES, {"title": "沒有網址"}])
        self.assertIn("提供的 1 則評論", build_maps_embed(body).description)


if __name__ == "__main__":
    unittest.main()
