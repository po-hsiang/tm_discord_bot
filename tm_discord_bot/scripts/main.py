from concurrent.futures import ThreadPoolExecutor
from functools import partial
import asyncio
import logging

from plugins.song_picker import SongPicker
from plugins.eat_what_system import EatWhatSystem
from plugins.remind_system import RemindSystem
from plugins.ai_agent_client import AIAgentClient
from plugins.auto_reply_system import AutoReplySystem
from plugins.video_summary import (
    SILENT_ERROR_CODES,
    VideoSummaryClient,
    build_embed,
    build_error_message,
    extract_video_id,
)
from config_utils import read_config_file
import discord

logger = logging.getLogger(__name__)

CONFIG = read_config_file()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 單一執行緒 worker：原生指令的外部呼叫（Google Sheets／歌單微服務）移出事件迴圈，
# 只開一條執行緒讓共享狀態（吃什麼清單載入）維持序列化存取
worker = ThreadPoolExecutor(max_workers=1)
# AI 專用執行緒池：n8n agent 帶工具可能跑數十秒，用獨立執行緒池
# 讓 AI 慢回覆不會卡住 !吃、!抽 等即時指令（AI 狀態都在 n8n 端，無共享狀態疑慮）
ai_worker = ThreadPoolExecutor(max_workers=4)

what_to_eat = EatWhatSystem()
yt_song = SongPicker()
ai_agent = AIAgentClient()
auto_reply_system = AutoReplySystem()
video_summary = VideoSummaryClient()

# 摘要進行中的影片（video_id → Future）：同影片同時被多人貼上時共用同一個請求，
# 不重複打 n8n / LLM；完成後自動移除（成功結果的 TTL 快取在 plugin 內）
_summary_inflight = {}

SONG_COMMAND_LIST = ["!聽", "!歌", "!聽歌", "!listen", "!song"]


def _pick_meal(meal_command):
    if meal_command in what_to_eat.get_meal_commend_list():
        return what_to_eat.choose_one_meal(meal_command)
    return None


def _preload_data():
    # 預載「吃什麼」清單；失敗時降級，之後使用時會再重試
    # （歌單的載入與快取已由 yt-music-mcp 微服務負責，不需預載）
    what_to_eat.ensure_loaded()


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


async def send_in_chunks(channel, content, chunk_size=1900, reply_to=None):
    # Discord 單則訊息上限 2000 字，超過就分段送出；
    # reply_to 指定時，第一段以「回覆」形式呈現（多人頻道中對話脈絡更清楚）
    for i in range(0, len(content), chunk_size):
        chunk = content[i : i + chunk_size]
        if reply_to is not None and i == 0:
            await reply_to.reply(chunk)
        else:
            await channel.send(chunk)


async def _handle_command(message, user_msg, loop):
    # 指令路徑：以 ! 開頭的訊息走原生功能
    answer = await loop.run_in_executor(
        worker, partial(auto_reply_system.get_reply, user_msg)
    )
    if answer:
        await send_in_chunks(message.channel, f"{message.author.mention}\n{answer}")

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
                    await message.channel.send(f"{message.author.mention}\n{result}")
                else:
                    await message.channel.send(result)
        else:
            await message.channel.send(
                f"{message.author.mention}\n歌單內的歌標題都沒有「{keyword}」字元"
            )


async def _handle_video_summary(message, video_id, loop):
    # 摘要可能跑數十秒，用 ⏳ reaction 代替 typing indicator 讓使用者知道有在處理
    try:
        await message.add_reaction("⏳")
    except discord.HTTPException:
        pass

    future = _summary_inflight.get(video_id)
    if future is None:
        future = loop.run_in_executor(
            ai_worker, partial(video_summary.summarize, video_id)
        )
        _summary_inflight[video_id] = future
        future.add_done_callback(lambda _: _summary_inflight.pop(video_id, None))

    try:
        result = await future
    finally:
        try:
            await message.remove_reaction("⏳", client.user)
        except discord.HTTPException:
            pass

    if result.get("ok"):
        await message.reply(embed=build_embed(result))
    elif result.get("error_code") not in SILENT_ERROR_CODES:
        await message.reply(build_error_message(result))
    # 靜默錯誤碼（如超過 70 分鐘的影片）：不處理也不回應，只撤掉 ⏳


async def _handle_natural_message(message, user_msg, loop):
    # 非指令訊息：視為自然語言直接交給 AI（含純圖片/貼圖訊息）
    if not user_msg and not message.attachments and not message.stickers:
        return

    context = _build_ai_context(message)
    async with message.channel.typing():
        answer = await loop.run_in_executor(
            ai_worker, partial(ai_agent.ask, question=user_msg, **context)
        )
    if answer:
        await send_in_chunks(message.channel, answer, reply_to=message)


@client.event
async def on_ready():
    logger.info("機器人「%s」已上線。", client.user)
    asyncio.get_running_loop().run_in_executor(worker, _preload_data)
    reminder_system = RemindSystem(client, ai_agent, yt_song, executor=ai_worker)
    reminder_system.start()  # 啟動鬧鐘功能，定時提醒


@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        # 忽略機器人（含自己 ☆㊣⤦虎喵小粉絲➷㊣❥#4703）的發言，避免機器人互聊迴圈
        return

    channel_id = message.channel.id
    loop = asyncio.get_running_loop()

    # YouTube 影片快速摘要：專屬頻道（含測試頻道）貼影片連結即觸發，免指令
    if channel_id in (
        CONFIG.get("video_summary_channel_id"),
        CONFIG.get("test_channel_id"),
    ):
        video_id = extract_video_id(message.content)
        if video_id:
            await _handle_video_summary(message, video_id, loop)
            return
        if channel_id == CONFIG.get("video_summary_channel_id"):
            # 專屬頻道只處理影片連結，其他訊息靜默忽略
            return

    if (channel_id != CONFIG.get("assistant_channel_id")) and (
        channel_id != CONFIG.get("test_channel_id")
    ):
        return

    user_msg = message.content

    # 轉換全形驚嘆號
    if "！" in user_msg:
        user_msg = user_msg.replace("！", "!")

    if user_msg.startswith("!"):
        # 1) 特定指令優先
        await _handle_command(message, user_msg, loop)
    else:
        # 2) 沒有指令 → 自然語言 AI 對話（含純圖片/貼圖訊息）
        await _handle_natural_message(message, user_msg, loop)


if __name__ == "__main__":
    # root_logger=True：讓 discord.py 的 log 設定（時間戳格式、handler）
    # 同時套用到本專案所有模組的 logger，全部輸出走同一套格式
    client.run(CONFIG.get("discord_bot_token"), root_logger=True)
