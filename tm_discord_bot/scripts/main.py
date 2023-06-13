from plugins.two_choices_one_system import TwoChoicesOneSystem
from plugins.youtube_api import YouTubeAPIHandler
from plugins.eat_what_system import EatWhatSystem
from plugins.remind_system import start_reminders
from plugins.pull_system import PullSystem
from plugins.openai_api import OpenaiAPI
from plugins.auto_reply_system import AutoReplySystem
from config_utils import read_config_file
import discord

CONFIG = read_config_file()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

what_to_eat = EatWhatSystem()
yt_song = YouTubeAPIHandler()
chat_gpt = OpenaiAPI()
two_choice_game = TwoChoicesOneSystem(what_to_eat.total_answers_list)
pull_system = PullSystem()
auto_reply_system = AutoReplySystem()

SONG_COMMAND_LIST = ["!聽", "!歌", "!聽歌", "!listen", "!song"]


@client.event
async def on_ready():
    print(f"機器人「{client.user}」已上線。")
    start_reminders(client, chat_gpt, yt_song)  # 啟動鬧鐘功能


@client.event
async def on_message(message):
    if message.author == client.user:
        # 忽略機器人自己的發言 ☆㊣⤦虎喵小粉絲➷㊣❥#4703
        return

    if (
        message.channel.id == CONFIG.get("assistant_channel_id")
        and len(message.content) > 0
    ):
        user_msg = message.content

        # 轉換全形驚嘆號
        if "！" in user_msg:
            user_msg = user_msg.replace("！", "!")

        answer = auto_reply_system.get_reply(user_msg)
        if answer:
            await message.channel.send(f"{message.author.mention}\n{answer}")

        # 二選一
        if two_choice_game.is_running:
            result = two_choice_game.play(user_msg)
            if result:
                await message.channel.send(f"{result}")
        elif user_msg == "!21":
            result = two_choice_game.start_game()
            if result:
                await message.channel.send(f"{result}")

        if user_msg[0] == "!":
            check_meal = user_msg.replace("!", "")
            if check_meal in what_to_eat.get_meal_commend_list():
                meal = what_to_eat.choose_one_meal(check_meal)
                await message.channel.send(f"{message.author.mention} 「{meal}」")

        if user_msg in SONG_COMMAND_LIST:
            song = yt_song.choose_one_song()
            await message.channel.send(
                f"從虎喵的歌單內隨機挑了這首歌給 {message.author.mention} \n {song} "
            )

        if user_msg[0:4] == "!查歌單":
            keyword = user_msg[5:]
            results = yt_song.search_keyword_in_song_list(keyword)
            if results:
                for index, result in enumerate(results):
                    if index == 0:
                        await message.channel.send(
                            f"{message.author.mention}\n{result}"
                        )
                    else:
                        await message.channel.send(result)
            else:
                await message.channel.send(
                    f"{message.author.mention}\n歌單內的歌標題都沒有「{keyword}」字元"
                )


if __name__ == "__main__":
    client.run(CONFIG.get("discord_bot_token"))
