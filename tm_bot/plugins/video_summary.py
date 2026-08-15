import json
import logging
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

import discord
from dotenv import load_dotenv

# 本機直跑時從專案根載入 .env；Docker 部署由 compose.yaml 的 env_file 注入
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

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

# 支援的三種 YouTube 連結格式（影片 ID 固定 11 碼；/shorts/ 短影片不在此功能範圍）
_VIDEO_ID_PATTERNS = (
    re.compile(r"youtube\.com/watch\?(?:[^\s]*&)?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/live/([A-Za-z0-9_-]{11})"),
)


def extract_video_id(text):
    """從訊息文字取出第一個 YouTube 影片 ID；沒有影片連結時回傳 None。"""
    for pattern in _VIDEO_ID_PATTERNS:
        matched = pattern.search(text or "")
        if matched:
            return matched.group(1)
    return None


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


class VideoSummaryClient:
    """呼叫 n8n「yt-summary」工作流的 HTTP 客戶端。

    影片中繼資料與字幕由 yt-music-mcp 微服務取得、LLM 摘要由 n8n 端的
    Gemini 執行，bot 只負責轉交 video_id 並把結構化結果帶回 Discord。
    成功結果以 video_id 為鍵做記憶體 TTL 快取，同影片重複貼上不重打 LLM。
    """

    CACHE_TTL_SECONDS = 6 * 60 * 60

    def __init__(self):
        self.webhook_url = os.getenv("N8N_YT_SUMMARY_WEBHOOK_URL")
        self.secret = os.getenv("N8N_WEBHOOK_SECRET")
        # 逾時階梯最上層：bot 200 > n8n 190 > yt-music-mcp 180（上游留封包餘裕）
        self.timeout = int(os.getenv("N8N_YT_SUMMARY_TIMEOUT", "200"))
        if not self.webhook_url or not self.secret:
            raise RuntimeError(
                "缺少 N8N_YT_SUMMARY_WEBHOOK_URL 或 N8N_WEBHOOK_SECRET 環境變數，"
                "請依 .env.example 設定 .env（Docker 部署經 compose.yaml 的 env_file 注入）"
            )
        # 快取由 ai_worker 執行緒池的多條執行緒共用，讀寫都上鎖
        self._cache = {}
        self._cache_lock = threading.Lock()

    def summarize(self, video_id):
        """回傳 n8n 契約的 dict（ok / summary / error_code）；保證不拋例外。"""
        with self._cache_lock:
            cached = self._cache.get(video_id)
            if cached and cached[0] > time.monotonic():
                return cached[1]

        result = self._request(video_id)
        if result.get("ok"):
            with self._cache_lock:
                self._cache[video_id] = (
                    time.monotonic() + self.CACHE_TTL_SECONDS,
                    result,
                )
        return result

    def _request(self, video_id):
        payload = {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        try:
            req = urllib.request.Request(
                self.webhook_url,
                method="POST",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Secret": self.secret,
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                body = json.loads(res.read().decode("utf-8"))
        except Exception as e:
            logger.error("呼叫 n8n yt-summary 失敗：%s", e)
            return {"ok": False, "error_code": "UPSTREAM_ERROR"}

        if not isinstance(body, dict):
            return {"ok": False, "error_code": "UPSTREAM_ERROR"}
        if body.get("ok"):
            if isinstance(body.get("summary"), dict):
                return body
            logger.warning("n8n 回應缺 summary，body 鍵：%s", list(body.keys()))
            return {"ok": False, "error_code": "SUMMARY_FAILED"}
        return {"ok": False, "error_code": str(body.get("error_code") or "UPSTREAM_ERROR")}
