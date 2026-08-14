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


class TestLunarFestivals(unittest.TestCase):
    """農曆人氣節日（cnlunar 離線換算，日期以萬年曆比對過）。"""

    def test_qixi_2026(self):
        self.assertEqual(get_holiday_info(date(2026, 8, 19)), (KIND_FESTIVAL, "七夕情人節"))

    def test_qixi_2025_in_leap_month_year(self):
        # 2025 有閏六月，真七夕在閏月之後：換算仍要正確
        self.assertEqual(get_holiday_info(date(2025, 8, 29)), (KIND_FESTIVAL, "七夕情人節"))

    def test_lantern_festival(self):
        self.assertEqual(get_holiday_info(date(2026, 3, 3)), (KIND_FESTIVAL, "元宵節"))

    def test_ghost_festival(self):
        self.assertEqual(get_holiday_info(date(2026, 8, 27)), (KIND_FESTIVAL, "中元節"))

    def test_double_ninth_festival(self):
        self.assertEqual(get_holiday_info(date(2026, 10, 18)), (KIND_FESTIVAL, "重陽節"))

    def test_leap_month_day_is_not_a_festival(self):
        # 2006-08-30 為閏七月初七：沒有閏月防呆會被誤判成七夕
        self.assertIsNone(get_holiday_info(date(2006, 8, 30)))


class TestSolarTerms(unittest.TestCase):
    def test_winter_solstice(self):
        self.assertEqual(get_holiday_info(date(2026, 12, 22)), (KIND_FESTIVAL, "冬至"))

    def test_start_of_winter(self):
        self.assertEqual(get_holiday_info(date(2026, 11, 7)), (KIND_FESTIVAL, "立冬"))

    def test_non_whitelisted_term_is_ignored(self):
        # 2026-03-20 春分：不在白名單（只收立冬、冬至），避免每 15 天就一個彩蛋
        self.assertIsNone(get_holiday_info(date(2026, 3, 20)))


class TestOrdinaryDays(unittest.TestCase):
    def test_plain_day_returns_none(self):
        self.assertIsNone(get_holiday_info(date(2026, 8, 14)))

    def test_non_whitelisted_us_days_are_ignored(self):
        # 聖派翠克節、美國父親節（臺灣是 8/8）都不在白名單，不觸發彩蛋
        self.assertIsNone(get_holiday_info(date(2026, 3, 17)))
        self.assertIsNone(get_holiday_info(date(2026, 6, 21)))


if __name__ == "__main__":
    unittest.main()
