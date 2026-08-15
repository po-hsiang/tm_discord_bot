import configparser
import os
from pathlib import Path

from dotenv import load_dotenv

# tm_discord_bot/ 套件目錄；.env 在專案根（本機直跑時載入，
# Docker 部署由 compose.yaml 的 env_file 注入，容器內沒有 .env 也無妨）
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PACKAGE_ROOT.parent / ".env")

# 機敏值一律來自環境變數（.env）；此處為「回傳鍵 → 環境變數名」的對照
# （YouTube 相關金鑰已不需要：歌單功能由 yt-music-mcp 微服務負責）
_ENV_KEYS = {
    "discord_bot_token": "DISCORD_BOT_TOKEN",
    "google_credential_file": "GOOGLE_CREDENTIAL_FILE",
    "what_to_eat_url": "WHAT_TO_EAT_URL",
}

# 非機敏設定來自 config/config.ini；頻道 ID 需轉為 int（Discord ID 為數字）
_CHANNEL_KEYS = (
    "assistant_channel_id",
    "test_channel_id",
    "chitchat_channel_id",
    "video_summary_channel_id",
    "game_deals_channel_id",
)


def read_config_file():
    """整併後的設定讀取：.env（機敏）＋ config/config.ini（非機敏）。

    回傳 dict 的鍵與舊版 config.json 相容，既有模組不需改動；
    未填寫的選填設定（如 AI 頻道）回傳 None。
    """
    ini_path = PACKAGE_ROOT / "config" / "config.ini"
    parser = configparser.ConfigParser()
    if not parser.read(ini_path, encoding="utf-8"):
        raise RuntimeError(f"找不到設定檔 {ini_path}，請確認專案結構完整")

    config = {key: os.getenv(env_name) for key, env_name in _ENV_KEYS.items()}

    missing = [_ENV_KEYS[k] for k, v in config.items() if not v]
    if missing:
        raise RuntimeError(
            f"缺少機敏環境變數：{missing}，"
            "請依 .env.example 設定 .env（Docker 部署經 compose.yaml 的 env_file 注入）"
        )

    for key in _CHANNEL_KEYS:
        raw = parser.get("discord", key, fallback="").strip()
        config[key] = int(raw) if raw else None

    return config
