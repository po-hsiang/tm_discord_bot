"""!抽 —— 加權抽籤（黑／黃／彩虹，含 10 抽保底）。"""

from discord.ext import commands

from tm_bot.services.draw import PullSystem


class Draw(commands.Cog):
    def __init__(self):
        self.service = PullSystem()

    @commands.command(name="抽")
    async def draw(self, ctx, *, _rest=""):
        # 「!抽 xxx」帶了參數也照常抽，不要已讀不回
        await ctx.send(f"{ctx.author.mention}\n{self.service.pull_a_sticks()}")


async def setup(bot):
    await bot.add_cog(Draw())
