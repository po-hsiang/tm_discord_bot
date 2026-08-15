"""Discord 呈現層：把服務層的結構化結果轉成使用者看到的訊息與 Embed。"""

import discord

# 錯誤碼 → 給使用者的文案（錯誤碼由 n8n yt-summary workflow 的回應契約定義）
ERROR_MESSAGES = {
    "VIDEO_NOT_FOUND": "無法取得相關影片，請確認連結 🙏",
    "LIVE_STREAM": "這部影片在直播中，請選擇其他影片 🙏",
    "NO_TRANSCRIPT": "無法取得影片字幕，請選擇其他影片 🙏",
    "MUSIC_CONTENT": "音樂類影片不支援摘要，請選擇其他影片 🙏",
    "SUMMARY_FAILED": "分析結果不符合預期格式，請再試一次 🙏",
    "UPSTREAM_ERROR": "機器人似乎出了點小差錯，請稍後再試 🙏",
}

# 這些錯誤碼靜默處理：不回覆使用者（超過 70 分鐘的影片直接不處理，僅入成本報告）
SILENT_ERROR_CODES = {"VIDEO_TOO_LONG"}


def _format_duration(seconds):
    minutes, sec = divmod(int(seconds or 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def build_error_message(result):
    return ERROR_MESSAGES.get(result.get("error_code"), ERROR_MESSAGES["UPSTREAM_ERROR"])


def build_embed(result):
    """把 n8n 摘要結果組成 Discord Embed（description 上限 4096，超長時截斷）。

    summary 契約：{"重點大綱": [每點一句話, ...], "影片標籤": "#tag1 #tag2"}
    （重點 2～4 點由 n8n 端保證；影片標籤為選填單行字串）。
    """
    summary = result.get("summary") or {}
    points = summary.get("重點大綱") or []
    description = "\n".join(f"• {point}" for point in points)
    tags = str(summary.get("影片標籤") or "").strip()
    if tags:
        description = f"{description}\n\n{tags}" if description else tags
    if len(description) > 4000:
        description = description[:4000] + "…\n*（內容過長，已截斷）*"

    embed = discord.Embed(
        title=str(result.get("title") or "")[:256],
        url=result.get("video_url") or None,
        description=description,
        color=0xFF0000,  # YouTube 紅
    )
    if result.get("thumbnail_url"):
        embed.set_thumbnail(url=result["thumbnail_url"])
    channel_name = str(result.get("channel") or "").strip()
    duration = _format_duration(result.get("duration_seconds"))
    embed.set_footer(
        text=f"{channel_name}｜片長 {duration}" if channel_name else f"片長 {duration}"
    )
    return embed
