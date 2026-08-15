"""非指令訊息（含純圖片／貼圖）交給 n8n AI Agent 回覆。"""

from discord.ext import commands

from tm_bot.ui.chunking import send_in_chunks


def build_context(message):
    """把訊息的使用者資訊與附件整理成 n8n webhook 契約需要的欄位。"""
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


class AiChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def reply(self, message):
        if not message.content and not message.attachments and not message.stickers:
            return

        context = build_context(message)
        # 打字中指示器：AI 可能跑數十秒，讓使用者知道有在處理
        async with message.channel.typing():
            answer = await self.bot.run_ai(
                self.bot.ai_agent.ask, question=message.content, **context
            )
        if answer:
            await send_in_chunks(message.channel, answer, reply_to=message)


async def setup(bot):
    await bot.add_cog(AiChat(bot))
