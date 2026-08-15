"""與 n8n webhook 溝通的共用 HTTP 呼叫。

兩個 n8n 客戶端（AI Agent、影片摘要）過去各自手刻一份 urllib POST、
Header Auth 與錯誤處理，幾乎逐行重複；統一於此並改用 requests
（本專案已相依，連線池與錯誤處理都比手刻的完整），全專案只留一套 HTTP 疊層。
"""

import requests

WEBHOOK_SECRET_HEADER = "X-Webhook-Secret"


class WebhookError(Exception):
    """呼叫 n8n webhook 失敗：連線異常、逾時、非 2xx、或回應不是 JSON 物件。"""


def post_json(url, payload, secret, timeout):
    """送出 JSON POST 並回傳解析後的 dict；任何失敗一律轉成 WebhookError。

    呼叫端只需處理 WebhookError 一種例外，各自決定要回什麼降級訊息。
    """
    try:
        response = requests.post(
            url,
            json=payload,
            headers={WEBHOOK_SECRET_HEADER: secret},
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        raise WebhookError(str(e)) from e

    if not isinstance(body, dict):
        raise WebhookError(f"回應不是 JSON 物件（{type(body).__name__}）")
    return body
