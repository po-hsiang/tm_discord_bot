"""進入點：`python -m tm_bot`。"""

from tm_bot.bot import create_bot


def main():
    bot = create_bot()
    # root_logger=True：讓 discord.py 的 log 設定（時間戳格式、handler）
    # 同時套用到本專案所有模組的 logger，全部輸出走同一套格式
    bot.run(bot.settings.discord_bot_token, root_logger=True)


if __name__ == "__main__":
    main()
