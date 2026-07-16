from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio

from plugins.youtube_api import YouTubeAPIHandler
from plugins.eat_what_system import EatWhatSystem
from plugins.remind_system import RemindSystem
from plugins.openai_api import OpenaiAPI
from plugins.auto_reply_system import AutoReplySystem
from config_utils import read_config_file
import discord

CONFIG = read_config_file()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 單一執行緒 worker：外部 API（OpenAI／Google Sheets／YouTube）皆為同步阻塞呼叫，
# 移到 worker 執行緒執行以免凍結 Discord 事件迴圈；只開一條執行緒是為了讓
# 共享狀態（GPT 對話歷史、淘汰賽進度）維持原本的序列化存取行為
worker = ThreadPoolExecutor(max_workers=1)

what_to_eat = EatWhatSystem()
yt_song = YouTubeAPIHandler()
chat_gpt = OpenaiAPI()
auto_reply_system = AutoReplySystem(
    yt_song=yt_song, chat_gpt=chat_gpt, what_to_eat=what_to_eat
)

SONG_COMMAND_LIST = ["!聽", "!歌", "!聽歌", "!listen", "!song"]


def _pick_meal(meal_command):
    if meal_command in what_to_eat.get_meal_commend_list():
        return what_to_eat.choose_one_meal(meal_command)
    return None


def _preload_data():
    # 預載「吃什麼」清單與歌單；失敗時各自降級，之後使用時會再重試
    what_to_eat.ensure_loaded()
    yt_song.ensure_loaded()


@client.event
async def on_ready():
    print(f"機器人「{client.user}」已上線。")
    asyncio.get_running_loop().run_in_executor(worker, _preload_data)
    reminder_system = RemindSystem(client, chat_gpt, yt_song, executor=worker)
    reminder_system.start()  # 啟動鬧鐘功能，定時提醒


@client.event
async def on_message(message):
    if message.author == client.user:
        # 忽略機器人自己的發言 ☆㊣⤦虎喵小粉絲➷㊣❥#4703
        return

    if len(message.content) <= 0:
        return

    channel_id = message.channel.id
    if (channel_id == CONFIG.get("assistant_channel_id")) or (
        channel_id == CONFIG.get("test_channel_id")
    ):
        user_msg = message.content
        loop = asyncio.get_running_loop()

        # 轉換全形驚嘆號
        if "！" in user_msg:
            user_msg = user_msg.replace("！", "!")

        answer = await loop.run_in_executor(
            worker, partial(auto_reply_system.get_reply, user_msg)
        )
        if answer:
            await message.channel.send(f"{message.author.mention}\n{answer}")

        if user_msg[0] == "!":
            check_meal = user_msg.replace("!", "")
            meal = await loop.run_in_executor(worker, partial(_pick_meal, check_meal))
            if meal:
                await message.channel.send(f"{message.author.mention} 「{meal}」")

        if user_msg in SONG_COMMAND_LIST:
            song = await loop.run_in_executor(worker, yt_song.choose_one_song)
            await message.channel.send(
                f"從虎喵的歌單內隨機挑了這首歌給 {message.author.mention} \n {song} "
            )

        if user_msg.startswith("!查歌單"):
            # 用指令長度切關鍵字並去除前後空白，「!查歌單abc」（沒打空格）也不會吃字
            keyword = user_msg[len("!查歌單"):].strip()
            results = await loop.run_in_executor(
                worker, partial(yt_song.search_keyword_in_song_list, keyword)
            )
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
