from pathlib import Path
import json
import logging
import os
import urllib.request

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 本機直跑時從專案根載入 .env；Docker 部署由 compose.yaml 的 env_file 注入
# （容器內沒有 .env 檔案，load_dotenv 對不存在的路徑是 no-op）
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

API_FAIL_MESSAGE = "小粉絲的 AI 大腦暫時連不上線，請稍後再試 🙏"
EMPTY_QUESTION_MESSAGE = "想問什麼呢？請在指令後面接上問題，例如：「!問 今天晚餐吃什麼好？」"


class AIAgentClient:
    """呼叫 n8n「TM AI Agent」工作流的 HTTP 客戶端。

    AI 模型、人設、工具與對話記憶全部由 n8n 端維護（各自獨立演進），
    bot 只負責把訊息與附件轉交過去、把回覆帶回 Discord。
    記憶以 channel_id 為 session key（n8n Simple Memory），
    傳入不同的 channel_id 即可隔離對話（例如早安排程用 morning-call）。
    """

    def __init__(self):
        self.webhook_url = os.getenv("N8N_AGENT_WEBHOOK_URL")
        self.secret = os.getenv("N8N_WEBHOOK_SECRET")
        self.timeout = int(os.getenv("N8N_AGENT_TIMEOUT", "60"))
        if not self.webhook_url or not self.secret:
            raise RuntimeError(
                "缺少 N8N_AGENT_WEBHOOK_URL 或 N8N_WEBHOOK_SECRET 環境變數，"
                "請依 .env.example 設定 .env（Docker 部署經 compose.yaml 的 env_file 注入）"
            )

    def ask(self, *args, **kwargs):
        question = str(kwargs.get("question") or "").strip()
        images = kwargs.get("images") or []
        stickers = kwargs.get("stickers") or []
        if not question and not images and not stickers:
            return EMPTY_QUESTION_MESSAGE

        # 呼叫端可傳 timeout 覆寫預設逾時（如晚間話題需等 n8n 端工具抓取，較慢）
        timeout = kwargs.get("timeout") or self.timeout
        payload = {
            "text": question,
            "user_name": kwargs.get("user_name") or "",
            "user_id": kwargs.get("user_id") or "",
            "channel_id": kwargs.get("channel_id") or "",
            "images": images,
            "stickers": stickers,
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
            with urllib.request.urlopen(req, timeout=timeout) as res:
                body = json.loads(res.read().decode("utf-8"))
            reply = str(body.get("reply") or "").strip()
            if reply:
                return reply
            logger.warning("n8n 回覆為空，body 鍵：%s", list(body.keys()))
            return API_FAIL_MESSAGE
        except Exception as e:
            logger.error("呼叫 n8n webhook 失敗：%s", e)
            return API_FAIL_MESSAGE
