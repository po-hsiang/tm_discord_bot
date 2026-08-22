import unittest

from tests.factories import make_settings
from tm_bot.bot import ROUTE_AI, ROUTE_COMMAND, ROUTE_IGNORE, ROUTE_VIDEO, TmBot

ASSISTANT = 111
TEST = 222
CHITCHAT = 333
VIDEO = 555
OUTSIDE = 999

VIDEO_LINK = "這部超好笑 https://youtu.be/dQw4w9WgXcQ"
# 只有 YouTube 連結有專屬路線，其餘連結一律當普通訊息
OTHER_LINK = "https://maps.app.goo.gl/AbCdEf123"


def route_of(bot, channel_id, content):
    return bot.classify(channel_id, content)[0]


def shutdown(bot):
    bot.worker.shutdown(wait=False)
    bot.ai_worker.shutdown(wait=False)


class TestClassify(unittest.TestCase):
    """訊息路由的守門規則：所有功能都經過這裡，行為必須被鎖住。"""

    @classmethod
    def setUpClass(cls):
        cls.bot = TmBot(
            make_settings(
                assistant_channel_id=ASSISTANT,
                test_channel_id=TEST,
                video_summary_channel_id=VIDEO,
            )
        )

    @classmethod
    def tearDownClass(cls):
        shutdown(cls.bot)

    def route(self, channel_id, content):
        return route_of(self.bot, channel_id, content)

    # --- 助手頻道 ---

    def test_command_in_assistant_channel(self):
        self.assertEqual(self.route(ASSISTANT, "!聽"), ROUTE_COMMAND)

    def test_plain_text_in_assistant_channel_goes_to_ai(self):
        self.assertEqual(self.route(ASSISTANT, "今天天氣如何"), ROUTE_AI)

    def test_empty_message_still_routes_to_ai(self):
        # 純圖片／貼圖訊息沒有文字，仍要交給 AI（由 Cog 判斷附件）
        self.assertEqual(self.route(ASSISTANT, ""), ROUTE_AI)

    # --- 影片摘要頻道 ---

    def test_video_link_in_dedicated_channel(self):
        route, video_id = self.bot.classify(VIDEO, VIDEO_LINK)
        self.assertEqual(route, ROUTE_VIDEO)
        self.assertEqual(video_id, "dQw4w9WgXcQ")

    def test_non_link_in_dedicated_channel_is_silently_ignored(self):
        # 專屬頻道只處理影片連結，其他訊息不回應、也不進 AI
        self.assertEqual(self.route(VIDEO, "大家好"), ROUTE_IGNORE)

    def test_command_in_dedicated_channel_is_ignored(self):
        self.assertEqual(self.route(VIDEO, "!聽"), ROUTE_IGNORE)

    # --- 測試頻道（兩種功能都吃）---

    def test_video_link_in_test_channel(self):
        self.assertEqual(self.route(TEST, VIDEO_LINK), ROUTE_VIDEO)

    def test_video_link_beats_ai_in_test_channel(self):
        # 測試頻道同時是 AI 頻道，含影片連結時以摘要優先，不可兩者都觸發
        self.assertNotEqual(self.route(TEST, VIDEO_LINK), ROUTE_AI)

    def test_plain_text_in_test_channel_goes_to_ai(self):
        self.assertEqual(self.route(TEST, "安安"), ROUTE_AI)

    # --- 非 YouTube 連結沒有專屬路線 ---

    def test_other_link_goes_to_ai(self):
        # 只有 YouTube 連結有專屬路線；其餘連結就是普通訊息，交給 AI
        self.assertEqual(self.route(ASSISTANT, OTHER_LINK), ROUTE_AI)
        self.assertEqual(self.route(TEST, OTHER_LINK), ROUTE_AI)

    def test_other_link_in_video_channel_is_ignored(self):
        self.assertEqual(self.route(VIDEO, OTHER_LINK), ROUTE_IGNORE)

    # --- 其他頻道 ---

    def test_chitchat_channel_is_ignored(self):
        # 閒聊頻道只收排程推播，不回應使用者訊息
        self.assertEqual(self.route(CHITCHAT, "!聽"), ROUTE_IGNORE)
        self.assertEqual(self.route(CHITCHAT, "安安"), ROUTE_IGNORE)

    def test_unknown_channel_is_ignored(self):
        self.assertEqual(self.route(OUTSIDE, "安安"), ROUTE_IGNORE)
        self.assertEqual(self.route(OUTSIDE, VIDEO_LINK), ROUTE_IGNORE)


class TestClassifyWithoutVideoChannel(unittest.TestCase):
    """未設定影片專屬頻道時（config.ini 留空），測試頻道仍應能觸發摘要。"""

    @classmethod
    def setUpClass(cls):
        cls.bot = TmBot(
            make_settings(
                assistant_channel_id=ASSISTANT,
                test_channel_id=TEST,
                video_summary_channel_id=None,
            )
        )

    @classmethod
    def tearDownClass(cls):
        shutdown(cls.bot)

    def test_video_link_in_test_channel(self):
        self.assertEqual(route_of(self.bot, TEST, VIDEO_LINK), ROUTE_VIDEO)

    def test_none_channel_id_does_not_swallow_other_channels(self):
        # video_summary_channel_id 為 None 時不可誤判成「任何頻道」
        self.assertEqual(route_of(self.bot, OUTSIDE, "安安"), ROUTE_IGNORE)


if __name__ == "__main__":
    unittest.main()
