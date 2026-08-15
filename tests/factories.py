"""測試用的假物件工廠。"""

from tm_bot.config import Settings


def make_settings(**overrides):
    """一組完整、不指向任何真實服務的設定。"""
    values = {
        "discord_bot_token": "token",
        "assistant_channel_id": 111,
        "test_channel_id": 222,
        "chitchat_channel_id": 333,
        "video_summary_channel_id": None,
        "game_deals_channel_id": 444,
        "google_credential_file": "service-account.json",
        "what_to_eat_url": "https://docs.google.com/spreadsheets/d/xxx",
        "yt_music_api_url": "http://yt-music-mcp:8765",
        "n8n_agent_webhook_url": "http://n8n/webhook/tm-ai-agent",
        "n8n_yt_summary_webhook_url": "http://n8n/webhook/yt-summary",
        "n8n_webhook_secret": "secret",
        "n8n_agent_timeout": 60,
        "n8n_yt_summary_timeout": 200,
    }
    values.update(overrides)
    return Settings(**values)
