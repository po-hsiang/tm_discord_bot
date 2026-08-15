import json
import logging
import threading
import time
import urllib.request

logger = logging.getLogger(__name__)


class VideoSummaryClient:
    """呼叫 n8n「yt-summary」工作流的 HTTP 客戶端。

    影片中繼資料與字幕由 yt-music-mcp 微服務取得、LLM 摘要由 n8n 端的
    Gemini 執行，bot 只負責轉交 video_id 並把結構化結果帶回 Discord。
    成功結果以 video_id 為鍵做記憶體 TTL 快取，同影片重複貼上不重打 LLM。
    """

    CACHE_TTL_SECONDS = 6 * 60 * 60

    def __init__(self, webhook_url, secret, timeout=200):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout
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
