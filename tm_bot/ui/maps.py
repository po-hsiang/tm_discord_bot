"""Google Maps 評論摘要的 Discord 呈現。

與 `embeds.py`（YouTube 影片摘要）分開放：兩者的錯誤碼與版型都不相通，
擠在一起只會讓兩邊都難改。

## 版型為什麼長這樣（2026-08-17 主人看過實際輸出後定案）

一句話：**緊湊、只留有用的**。區塊之間單行不空行；不放地址（使用者本來就是貼連結來的，
點標題就能導航）；不放一句話總評（資訊量低於底下的條列）。

排序刻意是「可靠度遞減」：⭐ 評分（最可靠的彙總信號）→ 評論摘錄 → facts（結構化事實）
→ 樣本大小提醒 → 來源。

實測發現 Maps grounding 每次只撈到**一則左右**的評論（一家 649 則評論的店只回 1 則），
Google 自己那套跨全部評論的 `reviewSummary` 欄位台灣與中文都還不在支援範圍，
因此有兩個不能省的誠實裝置：

1. **樣本大小由程式算後明講**（`_provenance_line()`）：模型曾經只拿到一則評論卻回空的
   提醒，自我察覺不可靠。數的是**評論**而非來源筆數——來源清單混了一筆店家頁面，
   說「2 筆來源」會讓人誤以為看了兩則評論。
2. **負評區塊永遠顯示**：0 筆時明講「這次摘到的評論裡沒有出現負評」，
   而不是整段消失（使用者分不清是沒人抱怨還是壞掉了），也不是宣稱這家店沒有負評。

## facts 的渲染規則（重要，不要自己加聰明）

`facts.yes` ＝確定有、`facts.no` ＝確定沒有、**沒被列到 ＝ Google 沒登錄資料**。
Places API 對不知道的屬性是整個欄位不回傳，所以「沒出現」不等於「沒有」——
**只渲染兩份清單裡實際有的標籤，永遠不要從缺漏推論出「沒有 XX」。**

## 來源那行是規定，不是裝飾

Google 要求 grounded 內容要緊接著標示 Maps 來源、且使用者在一次互動內看得到。
主人希望版面精簡，因此壓成**最後一行小字**（原本是一整個欄位五行），
但不能整個移除。
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
# 目前實測經常只有 1 則，所以這條提醒會常出現——那是誠實而非 bug；
# 日後 Google 若放寬取得的評論量，提醒會自動消失
LOW_REVIEW_SAMPLE = 3

# grounding 回的來源混了「地點」與「評論」兩種，只有後者才算評論樣本
# （地點那筆是店家頁面，不是任何人的評論）。評論來源的網址帶這段路徑——
# 這是實測觀察到的形狀、官方文件未載明，所以辨識不出來時會走保守的降級措辭
REVIEW_URI_MARKER = "/maps/reviews"

# 來源壓成一行，太多筆會把那行撐長；順序即重要性，裁掉尾巴是安全的
MAX_SOURCES = 4

# facts 的標籤是中性名詞，由這裡決定「有／沒有」怎麼標
FACTS_YES_PREFIX = "✅"
FACTS_NO_PREFIX = "❌"

# 同一行內多個標籤的分隔符
INLINE_SEPARATOR = " · "

# Embed description 上限 4096，留一點餘裕給截斷提示
MAX_DESCRIPTION = 4000


def build_maps_error_message(result):
    return MAPS_ERROR_MESSAGES.get(result.get("error_code"), MAPS_ERROR_MESSAGES["UPSTREAM_ERROR"])


def build_maps_embed(result):
    """把 n8n 的評論摘要結果組成 Discord Embed。

    契約：
        place   = {"name", "address", "maps_uri", "rating", "rating_count"}
        review  = {"verdict", "positive": [...], "negative": [...], "caveat"}
        facts   = {"yes": [...], "no": [...], "price_level"}
        sources = [{"title", "uri"}, ...]
    除了 place.name 之外都是選填，缺哪一段就少呈現那一段。
    `place.address` 與 `review.verdict` 目前刻意不呈現（見模組 docstring），
    但契約仍保留欄位，日後要加回來不必動 n8n。
    """
    place = _as_dict(result.get("place"))
    review = _as_dict(result.get("review"))
    # facts 是後加的欄位；舊版 n8n 回應不含它，缺了就少呈現那兩行
    facts = _as_dict(result.get("facts"))
    sources = result.get("sources")

    return discord.Embed(
        title=str(place.get("name") or "").strip()[:256],
        url=str(place.get("maps_uri") or "").strip() or None,
        description=_build_description(place, review, facts, sources),
        color=MAPS_COLOR,
    ).set_footer(text="資料來源 Google Maps")


def _build_description(place, review, facts, sources):
    # 區塊之間單行不空行；每個 helper 回傳空字串代表「這段沒東西可講」
    lines = [
        _headline(place, facts),
        _review_block("👍 **好評**", review.get("positive")),
        # 負評永遠有區塊，措辭限定在「這次摘到的評論」，不擴大成對這家店的斷言
        _review_block("👎 **負評**", review.get("negative"))
        or "👎 **負評**\n• 這次摘到的評論裡沒有出現負評",
        _facts_line(FACTS_YES_PREFIX, facts.get("yes")),
        _facts_line(FACTS_NO_PREFIX, facts.get("no")),
        _sample_note(place, review, sources),
        _sources_line(sources),
    ]

    description = "\n".join(line for line in lines if line)
    if len(description) > MAX_DESCRIPTION:
        return description[:MAX_DESCRIPTION] + "…\n*（內容過長，已截斷）*"
    return description


def _headline(place, facts):
    """⭐ 評分　／　評論數　／　💰 價位——最可靠的資訊擺第一行。"""
    parts = []

    rating = place.get("rating")
    if rating:
        parts.append(f"⭐ **{rating}**")
    count = _as_int(place.get("rating_count"))
    if count:
        parts.append(f"{count:,} 則評論")
    price_level = str(facts.get("price_level") or "").strip()
    if price_level:
        parts.append(f"💰 {price_level}")

    return "　／　".join(parts)


def _review_block(heading, items):
    bullets = _bullets(items)
    return f"{heading}\n{bullets}" if bullets else ""


def _facts_line(prefix, labels):
    """把結構化事實壓成一行。

    只印清單裡實際有的標籤——`yes`／`no` 之外的一切都是「Google 沒登錄」，
    不是「沒有」，絕不可從缺漏推論。
    """
    if not isinstance(labels, list):
        return ""
    cleaned = [str(label).strip() for label in labels if str(label).strip()]
    if not cleaned:
        return ""
    return f"{prefix} {INLINE_SEPARATOR.join(cleaned)}"


def _sample_note(place, review, sources):
    """樣本大小提醒；樣本足夠時改讓模型的 caveat 講它自己的事。"""
    provenance = _provenance_line(place, sources)
    if provenance:
        return provenance

    caveat = str(review.get("caveat") or "").strip()
    # -# 是 Discord 的小字語法，用來放補充說明而不搶戲
    return f"-# ⚠️ {caveat}" if caveat else ""


def _provenance_line(place, sources):
    """引用的評論則數偏少時，明講這段摘要的樣本有多小。

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


def _sources_line(sources):
    """來源壓成最後一行小字：Google 要求標示出處，但不必佔掉整個欄位。

    連結文字改用「地點／評論 N」這類短標籤（Google 給的標題冗長到會撐爆版面），
    網址一律原樣使用其提供的 uri。
    """
    links = []
    review_index = 0
    for source in _valid_sources(sources)[:MAX_SOURCES]:
        uri = str(source["uri"]).strip()
        if REVIEW_URI_MARKER in uri.lower():
            review_index += 1
            label = f"評論{review_index}"
        else:
            label = "地點"
        # 角括號抑制 Discord 的預覽卡片，避免一則訊息展開成一整排卡片
        links.append(f"[{label}](<{uri}>)")

    return f"-# 來源：{INLINE_SEPARATOR.join(links)}" if links else ""


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


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_int(value):
    try:
        return int(value)
    except TypeError, ValueError:
        return None
