"""集中式設定：.env（機敏）＋ config/config.ini（非機敏）。

三個設計原則：

1. **單一讀取點**：只有本模組碰 os.getenv 與設定檔，其餘模組一律由建構子取得
   所需的值。過去 load_dotenv 散在四個模組、且以 parents[N] 硬數目錄層數，
   檔案一搬家就會靜默失效。
2. **惰性讀取**：get_settings() 首次呼叫時才載入，模組匯入不產生副作用，
   測試不需要 .env 也能匯入任何模組。
3. **一次列出缺漏**：缺哪些環境變數一口氣報完，不要讓人一個一個試錯。
"""

import configparser
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# 專案根目錄（tm_bot/ 的上一層）：.env、config/、secrets/ 皆位於此
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_INI_PATH = PROJECT_ROOT / "config" / "config.ini"
SECRETS_DIR = PROJECT_ROOT / "secrets"

# 必填機敏設定：「欄位名 → 環境變數名」對照
_REQUIRED_ENV = {
    "discord_bot_token": "DISCORD_BOT_TOKEN",
    "google_credential_file": "GOOGLE_CREDENTIAL_FILE",
    "what_to_eat_url": "WHAT_TO_EAT_URL",
    "yt_music_api_url": "YT_MUSIC_API_URL",
    "n8n_agent_webhook_url": "N8N_AGENT_WEBHOOK_URL",
    "n8n_yt_summary_webhook_url": "N8N_YT_SUMMARY_WEBHOOK_URL",
    "n8n_webhook_secret": "N8N_WEBHOOK_SECRET",
}

# 選填設定：「欄位名 →（環境變數名, 預設值）」
_OPTIONAL_INT_ENV = {
    "n8n_agent_timeout": ("N8N_AGENT_TIMEOUT", 60),
    # 逾時階梯最上層：bot 200 > n8n 190 > yt-music-mcp 180（上游留封包餘裕）
    "n8n_yt_summary_timeout": ("N8N_YT_SUMMARY_TIMEOUT", 200),
}

# 非機敏設定來自 config/config.ini 的 [discord] 區段；Discord ID 為數字，未填則為 None
_CHANNEL_KEYS = (
    "assistant_channel_id",
    "test_channel_id",
    "chitchat_channel_id",
    "video_summary_channel_id",
    "game_deals_channel_id",
)


@dataclass(frozen=True)
class Settings:
    """整個應用程式的設定快照，啟動時建立一次後不再變動。"""

    # --- Discord ---
    discord_bot_token: str
    assistant_channel_id: int | None
    test_channel_id: int | None
    chitchat_channel_id: int | None
    video_summary_channel_id: int | None
    game_deals_channel_id: int | None

    # --- Google Sheets（吃什麼清單）---
    google_credential_file: str
    what_to_eat_url: str

    # --- yt-music-mcp 歌單微服務 ---
    yt_music_api_url: str

    # --- n8n 微服務 ---
    n8n_agent_webhook_url: str
    n8n_yt_summary_webhook_url: str
    n8n_webhook_secret: str
    n8n_agent_timeout: int
    n8n_yt_summary_timeout: int

    @property
    def google_credential_path(self) -> Path:
        """GCP 服務帳戶憑證的完整路徑（不入版控，Docker 以唯讀 volume 掛載）。"""
        return SECRETS_DIR / self.google_credential_file

    def channel_id(self, key: str) -> int | None:
        """以 config.ini 的鍵名取頻道 ID（排程等需要以字串指定頻道的場合使用）。"""
        return getattr(self, key)


def _load_env_values() -> dict:
    # 本機直跑時載入 .env；Docker 部署由 compose.yaml 的 env_file 注入，
    # 容器內沒有 .env 檔案，load_dotenv 對不存在的路徑是 no-op
    load_dotenv(PROJECT_ROOT / ".env")

    values = {key: os.getenv(env_name) for key, env_name in _REQUIRED_ENV.items()}
    missing = [_REQUIRED_ENV[key] for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            f"缺少機敏環境變數：{missing}，"
            "請依 .env.example 設定 .env（Docker 部署經 compose.yaml 的 env_file 注入）"
        )

    for key, (env_name, default) in _OPTIONAL_INT_ENV.items():
        values[key] = int(os.getenv(env_name) or default)
    return values


def _load_channel_ids() -> dict:
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG_INI_PATH, encoding="utf-8"):
        raise RuntimeError(f"找不到設定檔 {CONFIG_INI_PATH}，請確認專案結構完整")

    channels = {}
    for key in _CHANNEL_KEYS:
        raw = parser.get("discord", key, fallback="").strip()
        channels[key] = int(raw) if raw else None
    return channels


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """載入並快取設定；重複呼叫回傳同一個實例。"""
    return Settings(**_load_env_values(), **_load_channel_ids())
