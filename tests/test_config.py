import unittest
from dataclasses import FrozenInstanceError
from unittest import mock

from tm_bot import config
from tm_bot.config import SECRETS_DIR, Settings


def make_settings(**overrides):
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


class TestSettingsAccessors(unittest.TestCase):
    def test_channel_id_lookup_by_ini_key(self):
        # 排程以字串指定頻道（config.ini 的鍵名），需能對應到欄位
        settings = make_settings()
        self.assertEqual(settings.channel_id("chitchat_channel_id"), 333)
        self.assertEqual(settings.channel_id("game_deals_channel_id"), 444)

    def test_unset_channel_is_none(self):
        self.assertIsNone(make_settings().channel_id("video_summary_channel_id"))

    def test_credential_path_points_into_secrets_dir(self):
        path = make_settings().google_credential_path
        self.assertEqual(path.parent, SECRETS_DIR)
        self.assertEqual(path.name, "service-account.json")

    def test_settings_are_immutable(self):
        # frozen dataclass：設定是啟動時的快照，執行期不應被改寫
        with self.assertRaises(FrozenInstanceError):
            make_settings().discord_bot_token = "changed"


class TestEnvValidation(unittest.TestCase):
    def test_missing_env_lists_every_missing_variable_at_once(self):
        # 缺漏一次列完，不要讓人一個一個試錯
        with (
            mock.patch.object(config, "load_dotenv"),
            mock.patch.dict("os.environ", {}, clear=True),
            self.assertRaises(RuntimeError) as ctx,
        ):
            config._load_env_values()

        message = str(ctx.exception)
        for env_name in config._REQUIRED_ENV.values():
            self.assertIn(env_name, message)

    def test_optional_timeouts_fall_back_to_defaults(self):
        env = dict.fromkeys(config._REQUIRED_ENV.values(), "x")
        with (
            mock.patch.object(config, "load_dotenv"),
            mock.patch.dict("os.environ", env, clear=True),
        ):
            values = config._load_env_values()

        self.assertEqual(values["n8n_agent_timeout"], 60)
        self.assertEqual(values["n8n_yt_summary_timeout"], 200)


if __name__ == "__main__":
    unittest.main()
