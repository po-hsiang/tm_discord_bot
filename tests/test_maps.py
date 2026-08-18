import unittest

from tm_bot.services.maps import extract_maps_url, is_bare_link

SHORT = "https://maps.app.goo.gl/AbCdEf123"
PLACE = "https://www.google.com/maps/place/%E9%BC%8E%E6%B3%B0%E8%B1%90/@25.03,121.56,17z"


class TestExtractMapsUrl(unittest.TestCase):
    def test_share_short_url(self):
        # 手機 App「分享」給的形式，實務上最常見
        self.assertEqual(extract_maps_url(SHORT), SHORT)

    def test_legacy_short_url(self):
        url = "https://goo.gl/maps/XyZ789"
        self.assertEqual(extract_maps_url(url), url)

    def test_place_url_with_coordinates(self):
        self.assertEqual(extract_maps_url(PLACE), PLACE)

    def test_regional_domain(self):
        # 台灣使用者常拿到 google.com.tw 的網址
        url = "https://www.google.com.tw/maps/place/Somewhere"
        self.assertEqual(extract_maps_url(url), url)

    def test_maps_subdomain(self):
        url = "https://maps.google.com/?cid=1234567890"
        self.assertEqual(extract_maps_url(url), url)

    def test_query_form_without_trailing_slash(self):
        url = "https://www.google.com/maps?q=25.03,121.56"
        self.assertEqual(extract_maps_url(url), url)

    def test_url_inside_message_text(self):
        self.assertEqual(extract_maps_url(f"這家超讚 {SHORT} 大家去吃"), SHORT)

    def test_trailing_punctuation_is_stripped(self):
        # 中文句末標點很容易黏在網址後面
        self.assertEqual(extract_maps_url(f"推薦這家：{SHORT}。"), SHORT)

    def test_angle_bracket_wrapped_url(self):
        # Discord 使用者常用 <網址> 抑制預覽卡片
        self.assertEqual(extract_maps_url(f"<{SHORT}>"), SHORT)

    def test_first_maps_url_wins(self):
        second = "https://maps.app.goo.gl/Second999"
        self.assertEqual(extract_maps_url(f"{SHORT} 還有 {second}"), SHORT)

    # --- 不該誤判的情況 ---

    def test_plain_text_returns_none(self):
        self.assertIsNone(extract_maps_url("今天要吃什麼"))

    def test_none_and_empty_input(self):
        self.assertIsNone(extract_maps_url(None))
        self.assertIsNone(extract_maps_url(""))

    def test_other_google_services_are_not_maps(self):
        self.assertIsNone(extract_maps_url("https://www.google.com/search?q=拉麵"))
        self.assertIsNone(extract_maps_url("https://docs.google.com/spreadsheets/d/xxx"))

    def test_youtube_link_is_not_maps(self):
        # 影片摘要與地圖摘要共用測試頻道，兩者絕不能互相誤判
        self.assertIsNone(extract_maps_url("https://youtu.be/dQw4w9WgXcQ"))

    def test_other_goo_gl_short_links_are_not_maps(self):
        self.assertIsNone(extract_maps_url("https://goo.gl/abcdef"))

    def test_lookalike_domain_is_rejected(self):
        self.assertIsNone(extract_maps_url("https://google.com.evil.example/maps/place/x"))


class TestIsBareLink(unittest.TestCase):
    """意圖分流：只貼連結＝要卡片，連結旁邊有話＝要對話（交給 AI Agent）。"""

    def test_link_only(self):
        self.assertTrue(is_bare_link(SHORT, SHORT))

    def test_link_with_surrounding_whitespace(self):
        self.assertTrue(is_bare_link(f"  {SHORT}\n", SHORT))

    def test_angle_bracket_wrapped(self):
        # 使用者用 <網址> 抑制預覽卡片，仍算只貼連結
        self.assertTrue(is_bare_link(f"<{SHORT}>", SHORT))

    def test_trailing_punctuation_only(self):
        self.assertTrue(is_bare_link(f"{SHORT}。", SHORT))
        self.assertTrue(is_bare_link(f"{SHORT}!!", SHORT))

    def test_question_beside_link_is_not_bare(self):
        self.assertFalse(is_bare_link(f"這家好吃嗎？{SHORT}", SHORT))

    def test_any_words_make_it_conversational(self):
        self.assertFalse(is_bare_link(f"{SHORT} 推", SHORT))
        self.assertFalse(is_bare_link(f"明天去這家 {SHORT}", SHORT))

    def test_two_links_are_not_bare(self):
        # 只扣掉第一個連結，剩下那個網址算「有話」——交給 AI 處理比較保險
        second = "https://maps.app.goo.gl/Second999"
        self.assertFalse(is_bare_link(f"{SHORT} {second}", SHORT))


if __name__ == "__main__":
    unittest.main()
