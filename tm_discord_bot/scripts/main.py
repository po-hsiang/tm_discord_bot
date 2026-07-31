from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio

from plugins.youtube_api import YouTubeAPIHandler
from plugins.eat_what_system import EatWhatSystem
from plugins.remind_system import RemindSystem
from plugins.ai_agent_client import AIAgentClient
from plugins.auto_reply_system import AutoReplySystem
from config_utils import read_config_file
import discord

CONFIG = read_config_file()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 單一執行緒 worker：原生指令的外部呼叫（Google Sheets／YouTube）移出事件迴圈，
# 只開一條執行緒讓共享狀態（淘汰賽進度、歌單載入）維持序列化存取
worker = ThreadPoolExecutor(max_workers=1)
# AI 專用執行緒池：n8n agent 帶工具可能跑數十秒，用獨立執行緒池
# 讓 AI 慢回覆不會卡住 !吃、!抽 等即時指令（AI 狀態都在 n8n 端，無共享狀態疑慮）
ai_worker = ThreadPoolExecutor(max_workers=4)

what_to_eat = EatWhatSystem()
yt_song = YouTubeAPIHandler()
ai_agent = AIAgentClient()
auto_reply_system = AutoReplySystem(
    yt_song=yt_song, ai_agent=ai_agent, what_to_eat=what_to_eat
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


def _build_ai_context(message):
    # 把訊息的使用者資訊與附件整理成 n8n webhook 契約需要的欄位
    return {
        "user_name": message.author.display_name,
        "user_id": str(message.author.id),
        "channel_id": str(message.channel.id),
        "images": [
            {"url": attachment.url}
            for attachment in message.attachments
            if (attachment.content_type or "").startswith("image/")
        ],
        "stickers": [
            {"name": sticker.name, "format": sticker.format.name, "url": sticker.url}
            for sticker in message.stickers
        ],
    }


async def send_in_chunks(channel, content, chunk_size=1900):
    # Discord 單則訊息上限 2000 字，超過就分段送出
    for i in range(0, len(content), chunk_size):
        await channel.send(content[i : i + chunk_size])


@client.event
async def on_ready():
    print(f"機器人「{client.user}」已上線。")
    asyncio.get_running_loop().run_in_executor(worker, _preload_data)
    reminder_system = RemindSystem(client, ai_agent, yt_song, executor=ai_worker)
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

        cmd = user_msg.split(" ", 1)[0]
        is_ai_command = cmd in auto_reply_system.ai_command_list
        context = _build_ai_context(message) if is_ai_command else {}
        executor = ai_worker if is_ai_command else worker

        answer = await loop.run_in_executor(
            executor, partial(auto_reply_system.get_reply, user_msg, **context)
        )
        if answer:
            await send_in_chunks(message.channel, f"{message.author.mention}\n{answer}")

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
