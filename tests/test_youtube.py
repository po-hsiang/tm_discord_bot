import unittest

from tm_bot.services.youtube import extract_video_id


class TestExtractVideoId(unittest.TestCase):
    def test_watch_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_watch_url_with_extra_params(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?list=PLxxx&v=dQw4w9WgXcQ&t=42s"),
            "dQw4w9WgXcQ",
        )

    def test_short_url_with_query(self):
        self.assertEqual(
            extract_video_id("https://youtu.be/dQw4w9WgXcQ?si=abc123"),
            "dQw4w9WgXcQ",
        )

    def test_live_url(self):
        self.assertEqual(
            extract_video_id("https://www.youtube.com/live/dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_url_inside_message_text(self):
        self.assertEqual(
            extract_video_id("這部超好笑 https://youtu.be/dQw4w9WgXcQ 快看"),
            "dQw4w9WgXcQ",
        )

    def test_plain_text_returns_none(self):
        self.assertIsNone(extract_video_id("今天晚餐吃什麼"))

    def test_shorts_url_not_supported(self):
        self.assertIsNone(extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ"))

    def test_none_and_empty_input(self):
        self.assertIsNone(extract_video_id(None))
        self.assertIsNone(extract_video_id(""))


if __name__ == "__main__":
    unittest.main()
