"""YouTube 影片快速摘要：專屬頻道貼上影片連結即觸發，免指令。"""

import asyncio
import contextlib

import discord
from discord.ext import commands

from tm_bot.services.youtube import extract_video_id
from tm_bot.ui.embeds import SILENT_ERROR_CODES, build_embed, build_error_message

WORKING_REACTION = "⏳"


class VideoSummary(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 摘要進行中的影片（video_id → Task）：同影片同時被多人貼上時共用同一個請求，
        # 不重複打 n8n / LLM；完成後自動移除（成功結果的 TTL 快取在客戶端內）
        self._inflight = {}

    async def try_handle(self, message):
        """訊息含 YouTube 影片連結就處理並回傳 True；否則回傳 False 交還給路由。"""
        video_id = extract_video_id(message.content)
        if video_id is None:
            return False
        await self._summarize(message, video_id)
        return True

    async def _summarize(self, message, video_id):
        # 摘要可能跑數十秒，用 ⏳ reaction 代替 typing indicator 讓使用者知道有在處理
        with contextlib.suppress(discord.HTTPException):
            await message.add_reaction(WORKING_REACTION)

        task = self._inflight.get(video_id)
        if task is None:
            task = asyncio.ensure_future(
                self.bot.run_ai(self.bot.video_summary.summarize, video_id)
            )
            self._inflight[video_id] = task
            task.add_done_callback(lambda _: self._inflight.pop(video_id, None))

        try:
            result = await task
        finally:
            with contextlib.suppress(discord.HTTPException):
                await message.remove_reaction(WORKING_REACTION, self.bot.user)

        if result.get("ok"):
            await message.reply(embed=build_embed(result))
        elif result.get("error_code") not in SILENT_ERROR_CODES:
            await message.reply(build_error_message(result))
        # 靜默錯誤碼（如超過 70 分鐘的影片）：不處理也不回應，只撤掉 ⏳


async def setup(bot):
    await bot.add_cog(VideoSummary(bot))
