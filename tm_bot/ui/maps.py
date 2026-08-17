"""Google Maps 評論摘要的 Discord 呈現。

與 `embeds.py`（YouTube 影片摘要）分開放：兩者的錯誤碼與版型都不相通，
擠在一起只會讓兩邊都難改。

## 版型為什麼長這樣（2026-08-17 實測後定案）

實測發現 Maps grounding 每次只撈到**一則左右**的評論（一家 649 則評論的店只回 1 則、
2,933 則的店有時整個失敗）。Google 自己那套跨全部評論的 `reviewSummary` 欄位
**台灣與中文都還不在支援範圍**。因此版型刻意做成「誠實版」，三個決定：

1. **評分掛帥**：`rating` 與 `rating_count` 是唯一真正可靠的彙總信號，
   拉到最前面當主角；不再重複放頁尾，避免同一組數字出現兩次。
2. **資料來源由程式交代，不信 LLM**：模型曾經只拿到一則評論卻回空的 caveat，
   自我察覺不可靠。改由 `_provenance_line()` 依實際**引用到的評論則數**計算
   （來源清單裡混了一筆店家頁面，不能當成評論算），確保永遠不會漏講也不會多報。
3. **負評區塊永遠顯示**：0 筆時明講「這次摘到的評論裡沒有出現負評」——
   而不是整段消失（使用者分不清是沒人抱怨還是壞掉了），也不是宣稱這家店沒有負評。

**來源欄位是規定而非裝飾**：Google 要求 grounded 內容要緊接著標示 Maps 來源、
且使用者在一次互動內看得到，因此來源固定放在 Embed 最後一欄，不因版面考量省略。
"""

import discord

# Google 品牌綠
MAPS_COLOR = 0x34A853

# 錯誤碼 → 給使用者的文案（錯誤碼由 n8n maps-review workflow 的回應契約定義）
MAPS_ERROR_MESSAGES = {
    "URL_UNRESOLVED": "這個地圖連結我認不出是哪個地點，換一個「分享」連結試試 🙏",
    "NOT_A_PLACE": "這看起來是路線或搜尋結果，麻煩貼單一地點的分享連結 🙏",
    "NO_REVIEW_DATA": "這個地點的評論太少，整理不出可靠的心得 🙏",
    "MISSING_SOURCES": "這次沒拿到 Google Maps 來源連結，依規定不能只貼摘要，請再試一次 🙏",
    "SUMMARY_FAILED": "分析結果不符合預期格式，請再試一次 🙏",
    "UPSTREAM_ERROR": "機器人似乎出了點小差錯，請稍後再試 🙏",
}

# 引用的評論少於這個則數就掛「樣本偏少」提醒。
# 目前實測幾乎都只有 1 則，所以這條提醒會經常出現——那是誠實而非 bug；
# 日後 Google 若放寬取得的評論量，提醒會自動消失
LOW_REVIEW_SAMPLE = 3

# grounding 回的來源混了「地點」與「評論」兩種，只有後者才算評論樣本
# （地點那筆是店家頁面，不是任何人的評論）。評論來源的網址帶這段路徑——
# 這是實測觀察到的形狀、官方文件未載明，所以辨識不出來時會走保守的降級措辭
REVIEW_URI_MARKER = "/maps/reviews"

# Embed 單一欄位上限 1024 字元，來源列太多會擠爆，取前幾筆就夠交代出處
MAX_SOURCES = 5

# Embed description 上限 4096，留一點餘裕給截斷提示
MAX_DESCRIPTION = 4000


def build_maps_error_message(result):
    return MAPS_ERROR_MESSAGES.get(result.get("error_code"), MAPS_ERROR_MESSAGES["UPSTREAM_ERROR"])


def build_maps_embed(result):
    """把 n8n 的評論摘要結果組成 Discord Embed。

    契約：
        place  = {"name", "address", "maps_uri", "rating", "rating_count"}
        review = {"verdict", "positive": [...], "negative": [...], "caveat"}
        sources = [{"title", "uri"}, ...]
    除了 place.name 之外都是選填，缺哪一段就少呈現那一段。
    """
    place = result.get("place") or {}
    review = result.get("review") or {}
    sources = result.get("sources")

    embed = discord.Embed(
        title=str(place.get("name") or "").strip()[:256],
        url=str(place.get("maps_uri") or "").strip() or None,
        description=_build_description(place, review, sources),
        color=MAPS_COLOR,
    )

    address = str(place.get("address") or "").strip()
    if address:
        embed.add_field(name="📍 地址", value=address[:1024], inline=False)

    formatted_sources = _format_sources(sources)
    if formatted_sources:
        embed.add_field(name="📎 Google Maps 來源", value=formatted_sources[:1024], inline=False)

    embed.set_footer(text="資料來源 Google Maps")
    return embed


def _build_description(place, review, sources):
    blocks = []

    # 1) 評分：唯一可靠的彙總信號，放最前面
    rating_line = _rating_line(place)
    if rating_line:
        blocks.append(rating_line)

    verdict = str(review.get("verdict") or "").strip()
    if verdict:
        blocks.append(f"**{verdict}**")

    positive = _bullets(review.get("positive"))
    if positive:
        blocks.append(f"👍 **好評**\n{positive}")

    # 2) 負評永遠有區塊；措辭限定在「這次摘到的評論」，不擴大成對這家店的斷言
    negative = _bullets(review.get("negative"))
    blocks.append(
        f"👎 **負評**\n{negative}" if negative else "👎 **負評**\n• 這次摘到的評論裡沒有出現負評"
    )

    # 3) 資料來源交代：程式自己算，不依賴模型的自我察覺
    provenance = _provenance_line(place, sources)
    if provenance:
        blocks.append(provenance)
    else:
        # 樣本足夠時，模型的 caveat 講的才是別的事（例如評論互相矛盾），此時才值得顯示
        caveat = str(review.get("caveat") or "").strip()
        if caveat:
            # -# 是 Discord 的小字語法，用來放補充說明而不搶戲
            blocks.append(f"-# ⚠️ {caveat}")

    description = "\n\n".join(blocks)
    if len(description) > MAX_DESCRIPTION:
        return description[:MAX_DESCRIPTION] + "…\n*（內容過長，已截斷）*"
    return description


def _rating_line(place):
    rating = place.get("rating")
    if not rating:
        return ""
    count = _as_int(place.get("rating_count"))
    if count:
        return f"⭐ **{rating}**　／　{count:,} 則評論"
    return f"⭐ **{rating}**"


def _provenance_line(place, sources):
    """引用的評論則數偏少時，明講這段摘要的樣本有多小。

    數的是「評論」而非「來源」：來源清單裡混了一筆店家頁面，
    講「2 筆來源」會讓人誤以為看了兩則評論，那正是這版要消除的失真。

    刻意不是小字：「這是從 1 則評論摘出來的」對判讀的影響很大，不該被當成附註。
    """
    if _count_sources(sources) == 0:
        return ""

    reviews = _count_review_sources(sources)
    if reviews >= LOW_REVIEW_SAMPLE:
        return ""
    if reviews == 0:
        # 有來源但辨識不出任何評論：不編數字，只說樣本不可靠
        return "⚠️ 這次沒有取得可對照的評論來源，內容僅供參考。"

    total_ratings = _as_int(place.get("rating_count"))
    if total_ratings and total_ratings > reviews:
        return (
            f"⚠️ 以上摘自 Google Maps 提供的 {reviews} 則評論，"
            f"不代表 {total_ratings:,} 則評論的整體風向。"
        )
    return f"⚠️ 以上摘自 Google Maps 提供的 {reviews} 則評論，樣本偏少僅供參考。"


def _bullets(items):
    if not isinstance(items, list):
        return ""
    lines = [f"• {str(item).strip()}" for item in items if str(item).strip()]
    return "\n".join(lines)


def _valid_sources(sources):
    if not isinstance(sources, list):
        return []
    return [
        source
        for source in sources
        if isinstance(source, dict) and str(source.get("uri") or "").strip()
    ]


def _count_sources(sources):
    return len(_valid_sources(sources))


def _count_review_sources(sources):
    return sum(
        1 for source in _valid_sources(sources) if REVIEW_URI_MARKER in str(source["uri"]).lower()
    )


def _format_sources(sources):
    lines = []
    for source in _valid_sources(sources)[:MAX_SOURCES]:
        uri = str(source["uri"]).strip()
        title = str(source.get("title") or "").strip() or "Google Maps"
        # 角括號抑制 Discord 的預覽卡片，避免一則訊息展開成一整排卡片
        lines.append(f"• [{title}](<{uri}>)")
    return "\n".join(lines)


def _as_int(value):
    try:
        return int(value)
    except TypeError, ValueError:
        return None
