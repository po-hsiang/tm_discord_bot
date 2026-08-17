"""Google Maps 評論摘要：指定頻道貼上地圖連結即觸發，免指令。

流程與 YouTube 影片摘要同一套模式（reaction 表示處理中、同標的去重、
成功貼 Embed／失敗貼文案），差別只在標的是地圖連結而非影片。
"""

import asyncio
import contextlib

import discord
from discord.ext import commands

from tm_bot.ui.maps import build_maps_embed, build_maps_error_message

WORKING_REACTION = "⏳"


class MapsReview(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 處理中的連結（url → Task）：同一個連結同時被多人貼上時共用一次請求。
        # 這是「不做兩次相同的工作」，不是快取——完成即移除，不留存任何 Maps 內容
        self._inflight = {}

    async def review(self, message, maps_url):
        """由路由在判定為地圖連結訊息時呼叫（網址已於路由端擷取）。"""
        # 解析＋grounding 可能跑十幾秒，用 ⏳ reaction 讓使用者知道有在處理
        with contextlib.suppress(discord.HTTPException):
            await message.add_reaction(WORKING_REACTION)

        task = self._inflight.get(maps_url)
        if task is None:
            task = asyncio.ensure_future(self.bot.run_ai(self.bot.maps_review.review, maps_url))
            self._inflight[maps_url] = task
            task.add_done_callback(lambda _: self._inflight.pop(maps_url, None))

        try:
            result = await task
        finally:
            with contextlib.suppress(discord.HTTPException):
                await message.remove_reaction(WORKING_REACTION, self.bot.user)

        if result.get("ok"):
            await message.reply(embed=build_maps_embed(result))
        else:
            await message.reply(build_maps_error_message(result))


async def setup(bot):
    await bot.add_cog(MapsReview(bot))
