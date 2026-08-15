import unittest

from tests.factories import make_settings
from tm_bot.bot import COG_AI_CHAT, COG_EAT, COG_VIDEO_SUMMARY, EXTENSIONS, TmBot

# 使用者實際會打的指令；改動這份清單等同改動對外行為
EXPECTED_COMMANDS = {"心結", "問", "抽", "聽", "查歌單"}
SONG_ALIASES = ("歌", "聽歌", "listen", "song")


class TestCogRegistration(unittest.IsolatedAsyncioTestCase):
    """實際建立 Bot 並掛載全部 Cog：指令名稱打錯、Cog 忘了註冊都會在這裡被抓到。"""

    async def asyncSetUp(self):
        self.bot = TmBot(make_settings())
        for extension in EXTENSIONS:
            await self.bot.load_extension(extension)

    async def asyncTearDown(self):
        self.bot.worker.shutdown(wait=False)
        self.bot.ai_worker.shutdown(wait=False)

    async def test_every_extension_loads(self):
        self.assertEqual(len(self.bot.extensions), len(EXTENSIONS))

    async def test_registered_command_names(self):
        self.assertEqual({command.name for command in self.bot.commands}, EXPECTED_COMMANDS)

    async def test_song_aliases_point_to_one_command(self):
        listen = self.bot.get_command("聽")
        self.assertIsNotNone(listen)
        for alias in SONG_ALIASES:
            self.assertIs(self.bot.get_command(alias), listen)

    async def test_retired_ai_command_alias(self):
        self.assertIs(self.bot.get_command("gpt"), self.bot.get_command("問"))

    async def test_router_cogs_are_reachable_by_name(self):
        # 路由以名稱查 Cog（熱重載後仍取得到最新實例），名稱錯了就會在執行期炸掉
        for name in (COG_EAT, COG_AI_CHAT, COG_VIDEO_SUMMARY):
            self.assertIsNotNone(self.bot.get_cog(name), f"找不到 Cog：{name}")

    async def test_builtin_help_command_is_disabled(self):
        self.assertIsNone(self.bot.help_command)


if __name__ == "__main__":
    unittest.main()
