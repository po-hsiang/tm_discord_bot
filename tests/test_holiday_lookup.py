import sys
import unittest
from datetime import date
from pathlib import Path

# holiday_lookup 位於 scripts/plugins/，需先加入 sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "tm_discord_bot" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugins.holiday_lookup import (  # noqa: E402
    KIND_FESTIVAL,
    KIND_MAKEUP,
    get_holiday_info,
)


class TestNationalHolidays(unittest.TestCase):
    """臺灣國定假日（holidays 套件離線計算，日期以官方行事曆比對過）。"""

    def test_mid_autumn_festival(self):
        self.assertEqual(get_holiday_info(date(2026, 9, 25)), (KIND_FESTIVAL, "中秋節"))

    def test_lunar_new_year_eve(self):
        self.assertEqual(get_holiday_info(date(2026, 2, 16)), (KIND_FESTIVAL, "農曆除夕"))

    def test_day_before_eve_is_relabeled(self):
        # 套件把小年夜也標成「農曆除夕」，連兩天同名時第一天要改稱小年夜
        self.assertEqual(get_holiday_info(date(2026, 2, 15)), (KIND_FESTIVAL, "小年夜"))


class TestMakeupHolidays(unittest.TestCase):
    def test_makeup_day_returns_makeup_kind_with_festival_name(self):
        # 2026-02-27 為和平紀念日（補假）
        self.assertEqual(get_holiday_info(date(2026, 2, 27)), (KIND_MAKEUP, "和平紀念日"))

    def test_festival_beats_makeup_on_collision(self):
        # 2027-12-24 既是行憲紀念日（補假）也是平安夜：節日彩蛋優先
        self.assertEqual(get_holiday_info(date(2027, 12, 24)), (KIND_FESTIVAL, "平安夜"))


class TestPopularFestivals(unittest.TestCase):
    """美系人氣節日白名單與內建暱稱表。"""

    def test_halloween(self):
        self.assertEqual(get_holiday_info(date(2026, 10, 31)), (KIND_FESTIVAL, "萬聖節"))

    def test_mothers_day_second_sunday_of_may(self):
        self.assertEqual(get_holiday_info(date(2026, 5, 10)), (KIND_FESTIVAL, "母親節"))

    def test_local_table_overrides_official_name(self):
        # 12/25 官方名稱為行憲紀念日，內建表蓋成更有梗的聖誕節
        self.assertEqual(get_holiday_info(date(2026, 12, 25)), (KIND_FESTIVAL, "聖誕節"))
        # 1/1 開國紀念日 → 元旦
        self.assertEqual(get_holiday_info(date(2027, 1, 1)), (KIND_FESTIVAL, "元旦"))

    def test_taiwan_fathers_day(self):
        self.assertEqual(get_holiday_info(date(2026, 8, 8)), (KIND_FESTIVAL, "父親節"))


class TestOrdinaryDays(unittest.TestCase):
    def test_plain_day_returns_none(self):
        self.assertIsNone(get_holiday_info(date(2026, 8, 14)))

    def test_non_whitelisted_us_days_are_ignored(self):
        # 聖派翠克節、美國父親節（臺灣是 8/8）都不在白名單，不觸發彩蛋
        self.assertIsNone(get_holiday_info(date(2026, 3, 17)))
        self.assertIsNone(get_holiday_info(date(2026, 6, 21)))


if __name__ == "__main__":
    unittest.main()
