import unittest

from tm_bot.ui import embeds


class TestBuildEmbed(unittest.TestCase):
    def _sample_result(self, **overrides):
        result = {
            "ok": True,
            "video_id": "dQw4w9WgXcQ",
            "title": "測試影片標題",
            "channel": "測試頻道",
            "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "duration_seconds": 3725,
            "summary": {
                "重點大綱": ["第一個重點", "第二個重點", "第三個重點"],
                "影片標籤": "#標籤一 #標籤二",
            },
        }
        result.update(overrides)
        return result

    def test_embed_contains_all_points(self):
        embed = embeds.build_embed(self._sample_result())
        self.assertEqual(embed.title, "測試影片標題")
        self.assertEqual(embed.url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIn("• 第一個重點", embed.description)
        self.assertIn("• 第三個重點", embed.description)
        # 影片標籤放在重點條列後（空一行）
        self.assertTrue(embed.description.endswith("\n\n#標籤一 #標籤二"))
        # 3725 秒 = 1:02:05
        self.assertIn("1:02:05", embed.footer.text)
        self.assertIn("測試頻道", embed.footer.text)

    def test_embed_without_tags(self):
        result = self._sample_result(summary={"重點大綱": ["重點A", "重點B"]})
        embed = embeds.build_embed(result)
        self.assertIn("• 重點A", embed.description)
        self.assertNotIn("#", embed.description)

    def test_long_description_truncated_within_discord_limit(self):
        result = self._sample_result()
        result["summary"]["重點大綱"] = ["很長的重點" * 100] * 20
        embed = embeds.build_embed(result)
        self.assertLessEqual(len(embed.description), 4096)
        self.assertIn("已截斷", embed.description)

    def test_missing_summary_fields_do_not_crash(self):
        embed = embeds.build_embed(self._sample_result(summary={}))
        self.assertEqual(embed.title, "測試影片標題")


class TestBuildErrorMessage(unittest.TestCase):
    def test_known_error_code(self):
        message = embeds.build_error_message({"error_code": "NO_TRANSCRIPT"})
        self.assertIn("字幕", message)

    def test_unknown_error_code_falls_back(self):
        message = embeds.build_error_message({"error_code": "WHATEVER"})
        self.assertEqual(message, embeds.ERROR_MESSAGES["UPSTREAM_ERROR"])

    def test_missing_error_code_falls_back(self):
        message = embeds.build_error_message({})
        self.assertEqual(message, embeds.ERROR_MESSAGES["UPSTREAM_ERROR"])

    def test_video_too_long_is_silent(self):
        # 超過 70 分鐘的影片：不回應使用者（訊息路由依此集合略過回覆）
        self.assertIn("VIDEO_TOO_LONG", embeds.SILENT_ERROR_CODES)
        self.assertNotIn("VIDEO_TOO_LONG", embeds.ERROR_MESSAGES)


if __name__ == "__main__":
    unittest.main()
