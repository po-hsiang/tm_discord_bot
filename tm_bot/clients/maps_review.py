"""呼叫 n8n「maps-review」工作流的 HTTP 客戶端。

地點解析與評論摘要都在 n8n 端完成（Maps Grounding Lite 解析短網址 →
Gemini 以 google_maps 工具 grounding），bot 只轉交網址並把結構化結果帶回 Discord。

**與影片摘要客戶端最大的差別：這裡刻意沒有 TTL 快取。**
Maps Platform 條款明文禁止 pre-fetch／cache／store Places 內容（僅 place ID 例外），
grounded 輸出的快取規則官方文件也未交代，保守起見一律不留存。
「同一個連結同時被多人貼上」的重複請求由 Cog 端的 in-flight 去重處理——
那是不做兩次相同的工作，而不是把內容存起來。
"""

import logging

from tm_bot.clients.http import WebhookError, post_json

logger = logging.getLogger(__name__)


class MapsReviewClient:
    def __init__(self, webhook_url, secret, timeout=120):
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    def review(self, maps_url):
        """回傳 n8n 契約的 dict（ok / place / review / sources / error_code）；保證不拋例外。"""
        try:
            body = post_json(self.webhook_url, {"url": maps_url}, self.secret, self.timeout)
        except WebhookError as e:
            logger.error("呼叫 n8n maps-review 失敗：%s", e)
            return {"ok": False, "error_code": "UPSTREAM_ERROR"}

        if not body.get("ok"):
            return {"ok": False, "error_code": str(body.get("error_code") or "UPSTREAM_ERROR")}
        return self._validated(body)

    @staticmethod
    def _validated(body):
        """契約檢查：缺了必要欄位就當成失敗，不要讓半殘的結果貼到頻道上。"""
        place = body.get("place")
        if not isinstance(place, dict) or not str(place.get("name") or "").strip():
            logger.warning("maps-review 回應缺 place.name，body 鍵：%s", list(body.keys()))
            return {"ok": False, "error_code": "SUMMARY_FAILED"}

        if not isinstance(body.get("review"), dict):
            logger.warning("maps-review 回應缺 review，body 鍵：%s", list(body.keys()))
            return {"ok": False, "error_code": "SUMMARY_FAILED"}

        # Google 要求 grounded 內容必須附上 Maps 來源連結，因此「沒有來源」視為失敗：
        # 寧可不貼，也不要貼一段沒有出處的摘要
        if not _has_usable_source(body.get("sources")):
            logger.warning("maps-review 回應沒有可用的 sources，依規定不顯示摘要")
            return {"ok": False, "error_code": "MISSING_SOURCES"}

        return body


def _has_usable_source(sources):
    if not isinstance(sources, list):
        return False
    return any(
        isinstance(source, dict) and str(source.get("uri") or "").strip() for source in sources
    )
