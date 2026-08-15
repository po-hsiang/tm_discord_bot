import unittest

from tm_bot.bot import COMMANDS_ACCEPTING_ARGS, insert_missing_space


class TestInsertMissingSpace(unittest.TestCase):
    """「!查歌單abc」沒打空格也要能用（舊版以字串長度切關鍵字，改用 Cog 後需先補空格）。"""

    def test_missing_space_is_inserted(self):
        self.assertEqual(insert_missing_space("!查歌單abc"), "!查歌單 abc")

    def test_existing_space_is_left_alone(self):
        self.assertEqual(insert_missing_space("!查歌單 abc"), "!查歌單 abc")

    def test_command_without_argument_is_unchanged(self):
        self.assertEqual(insert_missing_space("!查歌單"), "!查歌單")

    def test_other_commands_are_unchanged(self):
        self.assertEqual(insert_missing_space("!抽"), "!抽")
        self.assertEqual(insert_missing_space("!聽歌"), "!聽歌")

    def test_plain_message_is_unchanged(self):
        self.assertEqual(insert_missing_space("今天天氣如何"), "今天天氣如何")

    def test_search_command_is_registered_as_taking_args(self):
        # 這份清單是路由與指令定義之間的約定，改指令名時別忘了同步
        self.assertIn("查歌單", COMMANDS_ACCEPTING_ARGS)


if __name__ == "__main__":
    unittest.main()
