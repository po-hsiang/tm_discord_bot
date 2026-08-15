"""固定回覆彩蛋，以及已退役指令的轉換提示。"""

from discord.ext import commands

XINJIE_REPLY = "沒有心結啦！哪次心結了？\n然後新垣結衣已婚QQ"
RETIRED_AI_COMMAND_NOTICE = "現在不用指令囉！直接把想說的話打出來，我就會回覆你 ✨"


class Misc(commands.Cog):
    @commands.command(name="心結")
    async def xinjie(self, ctx):
        await ctx.send(f"{ctx.author.mention}\n{XINJIE_REPLY}")

    @commands.command(name="問", aliases=["gpt"])
    async def retired_ai_command(self, ctx, *, _rest=""):
        # 舊的 !問／!gpt 已退役（頻道直接支援自然語言對話）；帶參數時也要收得到提示
        await ctx.send(f"{ctx.author.mention}\n{RETIRED_AI_COMMAND_NOTICE}")


async def setup(bot):
    await bot.add_cog(Misc())
