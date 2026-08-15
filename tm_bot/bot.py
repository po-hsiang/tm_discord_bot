"""組裝點（composition root）與訊息路由。

這裡是唯一知道「所有零件怎麼拼起來」的地方：讀設定、建客戶端、掛 Cog、啟動排程。
指令與事件處理在 cogs/、領域邏輯在 services/、外部呼叫在 clients/，
依賴方向單向：cogs → services → clients，services 完全不認識 discord。
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import discord
from discord.ext import commands

from tm_bot.clients.ai_agent import AIAgentClient
from tm_bot.clients.yt_music import SongPicker
from tm_bot.clients.yt_summary import VideoSummaryClient
from tm_bot.config import get_settings
from tm_bot.services.eat import EatWhatSystem
from tm_bot.services.scheduler.jobs import build_jobs
from tm_bot.services.scheduler.runner import Scheduler
from tm_bot.services.youtube import extract_video_id

logger = logging.getLogger(__name__)

COMMAND_PREFIX = "!"

# 掛載的 Cog（一個功能一個模組）。以 load_extension 載入而非直接 add_cog，
# 日後才能用 reload_extension 熱重載，不必重開容器
EXTENSIONS = (
    "tm_bot.cogs.misc",
    "tm_bot.cogs.draw",
    "tm_bot.cogs.song",
    "tm_bot.cogs.eat",
    "tm_bot.cogs.ai_chat",
    "tm_bot.cogs.video_summary",
)

# Cog 的名稱（qualified_name）；路由以名稱查詢，熱重載後仍取得到最新的實例
COG_EAT = "Eat"
COG_AI_CHAT = "AiChat"
COG_VIDEO_SUMMARY = "VideoSummary"

# 需要接參數的指令：使用者常常不打空格（「!查歌單abc」），
# discord.py 會把整串當成指令名而找不到指令，於是在此補回空格
COMMANDS_ACCEPTING_ARGS = ("查歌單",)

# 訊息路線
ROUTE_IGNORE = "ignore"  # 不屬於本機器人服務範圍，靜默忽略
ROUTE_VIDEO = "video"  # 影片快速摘要
ROUTE_COMMAND = "command"  # ! 開頭的指令
ROUTE_AI = "ai"  # 自然語言對話


def insert_missing_space(content, prefix=COMMAND_PREFIX):
    """把「!查歌單abc」補成「!查歌單 abc」；其餘內容原樣回傳。"""
    if not content.startswith(prefix):
        return content
    body = content[len(prefix) :]
    for name in COMMANDS_ACCEPTING_ARGS:
        if body.startswith(name) and len(body) > len(name) and not body[len(name)].isspace():
            return f"{prefix}{name} {body[len(name) :]}"
    return content


class TmBot(commands.Bot):
    """虎喵小粉絲本體：持有共用的客戶端、服務與執行緒池，供各 Cog 取用。"""

    def __init__(self, settings):
        intents = discord.Intents.default()
        intents.message_content = True
        # help_command=None：不要 discord.py 內建的 !help（本專案沒這個功能）
        super().__init__(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

        self.settings = settings
        self._preload_task = None

        # 單一執行緒 worker：原生指令的外部呼叫（Google Sheets／歌單微服務）移出事件迴圈，
        # 只開一條執行緒讓共享狀態（吃什麼清單載入）維持序列化存取
        self.worker = ThreadPoolExecutor(max_workers=1)
        # AI 專用執行緒池：n8n agent 帶工具可能跑數十秒，用獨立執行緒池
        # 讓 AI 慢回覆不會卡住 !吃、!抽 等即時指令（AI 狀態都在 n8n 端，無共享狀態疑慮）
        self.ai_worker = ThreadPoolExecutor(max_workers=4)

        self.ai_agent = AIAgentClient(
            settings.n8n_agent_webhook_url,
            settings.n8n_webhook_secret,
            settings.n8n_agent_timeout,
        )
        self.yt_song = SongPicker(settings.yt_music_api_url)
        self.video_summary = VideoSummaryClient(
            settings.n8n_yt_summary_webhook_url,
            settings.n8n_webhook_secret,
            settings.n8n_yt_summary_timeout,
        )
        self.what_to_eat = EatWhatSystem(settings.what_to_eat_url, settings.google_credential_path)
        self.scheduler = Scheduler(self, settings, executor=self.ai_worker)
        self.scheduler.add(*build_jobs(self.ai_agent, self.yt_song))

    # --- 阻塞呼叫的統一入口（避免每個 Cog 各自寫 run_in_executor + partial）---

    async def run_blocking(self, func, *args, **kwargs):
        """把阻塞呼叫丟到共用 worker（序列化，適合有共享狀態的功能）。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.worker, partial(func, *args, **kwargs))

    async def run_ai(self, func, *args, **kwargs):
        """把 AI 相關的慢速呼叫丟到獨立執行緒池，不排擠即時指令。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.ai_worker, partial(func, *args, **kwargs))

    # --- 生命週期 ---

    async def setup_hook(self):
        # setup_hook 只在啟動時執行一次（斷線重連不會再跑），
        # 是掛 Cog 與啟動排程的正確位置——過去放在 on_ready 才需要 Singleton 防重複
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        logger.info("已掛載 %d 個 Cog：%s", len(EXTENSIONS), ", ".join(self.cogs))

        # 預載「吃什麼」清單；失敗時降級，之後使用時會再重試
        # （歌單的載入與快取已由 yt-music-mcp 微服務負責，不需預載）
        # 保留 task 參考，避免執行中的預載被垃圾回收掉
        self._preload_task = asyncio.create_task(self.run_blocking(self.what_to_eat.ensure_loaded))

        self.scheduler.start()

    async def on_ready(self):
        logger.info("機器人「%s」已上線。", self.user)

    # --- 訊息路由 ---

    def _is_ai_channel(self, channel_id):
        return channel_id in (self.settings.assistant_channel_id, self.settings.test_channel_id)

    def _is_video_channel(self, channel_id):
        return channel_id in (
            self.settings.video_summary_channel_id,
            self.settings.test_channel_id,
        )

    def classify(self, channel_id, content):
        """決定一則訊息該走哪條路，回傳 (路線, 影片 ID)。

        純決策、不做任何 I/O，所有頻道守門規則集中在此，可單獨測試。
        """
        video_id = extract_video_id(content)

        # 1) YouTube 影片快速摘要：專屬頻道（含測試頻道）貼影片連結即觸發，免指令
        if self._is_video_channel(channel_id):
            if video_id is not None:
                return ROUTE_VIDEO, video_id
            if channel_id == self.settings.video_summary_channel_id:
                # 專屬頻道只處理影片連結，其他訊息靜默忽略
                return ROUTE_IGNORE, None

        # 2) 其餘功能只服務助手頻道與測試頻道
        if not self._is_ai_channel(channel_id):
            return ROUTE_IGNORE, None

        if content.startswith(COMMAND_PREFIX):
            return ROUTE_COMMAND, None
        # 3) 其餘任何訊息（含純圖片／貼圖）一律視為自然語言
        return ROUTE_AI, None

    async def on_message(self, message):
        # 忽略所有機器人（含自己）的發言，避免機器人互聊迴圈
        if message.author.bot:
            return

        # 全形驚嘆號轉半形，讓「！抽」也能觸發指令
        if "！" in message.content:
            message.content = message.content.replace("！", "!")

        route, video_id = self.classify(message.channel.id, message.content)

        if route == ROUTE_IGNORE:
            return
        if route == ROUTE_VIDEO:
            await self.get_cog(COG_VIDEO_SUMMARY).summarize(message, video_id)
            return
        if route == ROUTE_COMMAND:
            message.content = insert_missing_space(message.content)
            ctx = await self.get_context(message)
            if ctx.valid:
                await self.invoke(ctx)
                return
            # 沒有對應的指令 → 可能是「吃什麼」的動態分類（分類名來自試算表）
            await self.get_cog(COG_EAT).try_meal(message)
            return

        await self.get_cog(COG_AI_CHAT).reply(message)


def create_bot():
    return TmBot(get_settings())
