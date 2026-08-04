from pathlib import Path
import tempfile
import unittest

from tm_discord_bot.scripts.plugins import summary_report


def _success_result(**overrides):
    result = {
        "ok": True,
        "video_id": "dQw4w9WgXcQ",
        "title": "測試影片 <b>標題</b>",
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "duration_seconds": 214,
        "source": "audio",
        "summary": {"重點大綱": ["a", "b"]},
        "stats": {
            "transcript_chars": None,
            "input_tokens": 36832,
            "output_tokens": 122,
            "model": "gemini-3.1-flash-lite",
        },
    }
    result.update(overrides)
    return result


class TestAppendRecord(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.report_path = Path(self._tmp.name) / "report.html"

    def tearDown(self):
        self._tmp.cleanup()

    def _read(self):
        return self.report_path.read_text(encoding="utf-8")

    def test_creates_file_with_row(self):
        summary_report.append_record("dQw4w9WgXcQ", _success_result(), self.report_path)
        content = self._read()
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("36,832", content)
        self.assertIn("音訊轉錄", content)
        self.assertIn("✅ 成功", content)

    def test_title_html_escaped(self):
        summary_report.append_record("dQw4w9WgXcQ", _success_result(), self.report_path)
        content = self._read()
        self.assertNotIn("<b>標題</b>", content)
        self.assertIn("&lt;b&gt;標題&lt;/b&gt;", content)

    def test_appends_rows_on_subsequent_calls(self):
        summary_report.append_record("dQw4w9WgXcQ", _success_result(), self.report_path)
        summary_report.append_record("dQw4w9WgXcQ", _success_result(), self.report_path)
        self.assertEqual(self._read().count('<tr data-ok='), 2)

    def test_transcript_path_estimates_tokens(self):
        result = _success_result(
            source="transcript",
            stats={"transcript_chars": 2089, "input_tokens": None,
                   "output_tokens": None, "model": None},
        )
        summary_report.append_record("dQw4w9WgXcQ", result, self.report_path)
        content = self._read()
        self.assertIn("（估）", content)
        self.assertIn("2,089", content)
        self.assertIn("CC 字幕", content)
        self.assertIn("約 NT$", content)

    def test_failure_row_without_stats(self):
        result = {"ok": False, "error_code": "NO_TRANSCRIPT"}
        summary_report.append_record("dQw4w9WgXcQ", result, self.report_path)
        content = self._read()
        self.assertIn("❌ NO_TRANSCRIPT", content)
        self.assertIn('data-ok="0"', content)
        # 沒有 title 時以 video_id 呈現、連結仍可點
        self.assertIn(">dQw4w9WgXcQ</a>", content)

    def test_cost_calculation_uses_source_pricing(self):
        twd = summary_report._estimate_cost_twd("audio", 1_000_000, 0)
        expected = summary_report.PRICING_USD_PER_M["audio"]["input"] * summary_report.USD_TO_TWD
        self.assertAlmostEqual(twd, expected)
        self.assertIsNone(summary_report._estimate_cost_twd("unknown", 1000, 10))
        self.assertIsNone(summary_report._estimate_cost_twd("audio", None, 10))


if __name__ == "__main__":
    unittest.main()
