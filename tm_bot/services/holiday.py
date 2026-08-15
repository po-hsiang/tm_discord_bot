"""節日查詢：判斷今天是否為節日或補假，供早安排程加彩蛋。

五層合併、全離線計算（holidays＋cnlunar 套件本地演算，無網路呼叫）：
1. 內建暱稱表：非國定的人氣節日，並蓋過官方式名稱（行憲紀念日→聖誕節）
2. 臺灣國定假日（含補假，補假標明是補哪個節日）
3. 美系人氣節日白名單（US unofficial 分類，翻成臺灣慣用名）
4. 農曆人氣節日（七夕、元宵、中元、重陽；閏月不算）
5. 節氣白名單（只收有食俗梗的立冬、冬至，避免彩蛋通膨）

優先權：具名節日（1～4 層）＞補假＞節氣。
"""

from datetime import datetime, timedelta

import cnlunar
import holidays

KIND_FESTIVAL = "festival"  # 節日彩蛋
KIND_MAKEUP = "makeup"  # 連假的補假日（體恤出遊模式）

# 內建暱稱表（優先權最高）：key 為 (月, 日)
LOCAL_FESTIVALS = {
    (1, 1): "元旦",
    (8, 8): "父親節",
    (12, 25): "聖誕節",
}

# 美系人氣節日 → 臺灣慣用名；不在表上的（聖派翠克、土撥鼠節、美國父親節）一律忽略
US_UNOFFICIAL_ZH = {
    "Valentine's Day": "西洋情人節",
    "Mother's Day": "母親節",
    "Halloween": "萬聖節",
    "Christmas Eve": "平安夜",
    "New Year's Eve": "跨年夜",
}

MAKEUP_SUFFIX = "（補假）"

# 農曆人氣節日：key 為 (農曆月, 農曆日)
LUNAR_FESTIVALS = {
    (1, 15): "元宵節",
    (7, 7): "七夕情人節",
    (7, 15): "中元節",
    (9, 9): "重陽節",
}

# 節氣白名單：立冬（進補）、冬至（湯圓）兩字在簡繁相同可直接比對；
# 日後若要加驚蟄、穀雨等，注意 cnlunar 回傳的是簡體（惊蛰／谷雨），需另做對照
SOLAR_TERM_FESTIVALS = {"立冬", "冬至"}


def get_holiday_info(today):
    """回傳 (kind, 節日名)；kind 為 KIND_FESTIVAL 或 KIND_MAKEUP，平日回傳 None。"""
    local_name = LOCAL_FESTIVALS.get((today.month, today.day))
    if local_name:
        return (KIND_FESTIVAL, local_name)

    # 隔日查詢（小年夜判斷）可能跨年，兩個年份都先備好
    tw = holidays.country_holidays("TW", years={today.year, today.year + 1})
    makeup_name = None
    tw_name = tw.get(today)
    if tw_name:
        tw_name = tw_name.split("; ")[0]
        if tw_name.endswith(MAKEUP_SUFFIX):
            # 補假先記下不回傳：撞上人氣節日時（如 2027-12-24 補假遇平安夜）節日彩蛋優先
            makeup_name = tw_name.removesuffix(MAKEUP_SUFFIX)
        else:
            if tw_name == "農曆除夕" and tw.get(today + timedelta(days=1)) == "農曆除夕":
                # 套件把小年夜也標成除夕：連兩天同名時，第一天其實是小年夜
                tw_name = "小年夜"
            return (KIND_FESTIVAL, tw_name)

    us_name = _us_popular_name(today)
    if us_name:
        return (KIND_FESTIVAL, us_name)

    lunar = cnlunar.Lunar(datetime(today.year, today.month, today.day), godType="8char")
    if not lunar.isLunarLeapMonth:
        # 閏月不算節日（如 2006 年閏七月初七不是七夕，真七夕在下一個月）
        lunar_name = LUNAR_FESTIVALS.get((lunar.lunarMonth, lunar.lunarDay))
        if lunar_name:
            return (KIND_FESTIVAL, lunar_name)

    if makeup_name:
        return (KIND_MAKEUP, makeup_name)

    if lunar.todaySolarTerms in SOLAR_TERM_FESTIVALS:
        return (KIND_FESTIVAL, lunar.todaySolarTerms)
    return None


def _us_popular_name(today):
    """今天若是白名單內的美系人氣節日，回傳臺灣慣用名，否則 None。"""
    us = holidays.country_holidays("US", years=today.year, categories=("unofficial",))
    raw = us.get(today)
    if not raw:
        return None
    # 同一天可能掛多個名字（以「; 」相連），只認白名單內的
    for part in raw.split("; "):
        if part in US_UNOFFICIAL_ZH:
            return US_UNOFFICIAL_ZH[part]
    return None
