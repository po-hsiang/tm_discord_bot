"""Google Maps 評論摘要的 Discord 呈現。

與 `embeds.py`（YouTube 影片摘要）分開放：兩者的錯誤碼與版型都不相通，
擠在一起只會讓兩邊都難改。

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

    embed = discord.Embed(
        title=str(place.get("name") or "").strip()[:256],
        url=str(place.get("maps_uri") or "").strip() or None,
        description=_build_description(review),
        color=MAPS_COLOR,
    )

    address = str(place.get("address") or "").strip()
    if address:
        embed.add_field(name="📍 地址", value=address[:1024], inline=False)

    sources = _format_sources(result.get("sources"))
    if sources:
        embed.add_field(name="📎 Google Maps 來源", value=sources[:1024], inline=False)

    embed.set_footer(text=_build_footer(place))
    return embed


def _build_description(review):
    blocks = []

    verdict = str(review.get("verdict") or "").strip()
    if verdict:
        blocks.append(f"**{verdict}**")

    positive = _bullets(review.get("positive"))
    if positive:
        blocks.append(f"👍 **好評**\n{positive}")

    negative = _bullets(review.get("negative"))
    if negative:
        blocks.append(f"👎 **負評**\n{negative}")

    caveat = str(review.get("caveat") or "").strip()
    if caveat:
        # -# 是 Discord 的小字語法，用來放「資料有限」這類提醒而不搶戲
        blocks.append(f"-# ⚠️ {caveat}")

    description = "\n\n".join(blocks)
    if len(description) > MAX_DESCRIPTION:
        return description[:MAX_DESCRIPTION] + "…\n*（內容過長，已截斷）*"
    return description


def _bullets(items):
    if not isinstance(items, list):
        return ""
    lines = [f"• {str(item).strip()}" for item in items if str(item).strip()]
    return "\n".join(lines)


def _format_sources(sources):
    if not isinstance(sources, list):
        return ""

    lines = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        uri = str(source.get("uri") or "").strip()
        if not uri:
            continue
        title = str(source.get("title") or "").strip() or "Google Maps"
        # 角括號抑制 Discord 的預覽卡片，避免一則訊息展開成一整排卡片
        lines.append(f"• [{title}](<{uri}>)")
        if len(lines) >= MAX_SOURCES:
            break
    return "\n".join(lines)


def _build_footer(place):
    parts = []

    rating = place.get("rating")
    if rating:
        parts.append(f"⭐ {rating}")

    count = _as_int(place.get("rating_count"))
    if count:
        parts.append(f"{count:,} 則評論")

    # 歸屬字樣：Google 規定要標示 Maps 來源，空間有限時文字型態即可
    parts.append("資料來源 Google Maps")
    return "｜".join(parts)


def _as_int(value):
    try:
        return int(value)
    except TypeError, ValueError:
        return None
