"""!聽（隨機點歌）與 !查歌單（跨歌單搜尋）。"""

from discord.ext import commands


class Song(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="聽", aliases=["歌", "聽歌", "listen", "song"])
    async def listen(self, ctx, *, _rest=""):
        song = await self.bot.run_blocking(self.bot.yt_song.choose_one_song)
        await ctx.send(f"從虎喵的歌單內隨機挑了這首歌給 {ctx.author.mention} \n {song} ")

    @commands.command(name="查歌單")
    async def search(self, ctx, *, keyword=""):
        results = await self.bot.run_blocking(
            self.bot.yt_song.search_keyword_in_song_list, keyword.strip()
        )
        if not results:
            await ctx.send(f"{ctx.author.mention}\n歌單內的歌標題都沒有「{keyword.strip()}」字元")
            return
        # 搜尋結果可能超過 Discord 單則訊息上限，微服務端已切好段，逐段送出
        for index, result in enumerate(results):
            if index == 0:
                await ctx.send(f"{ctx.author.mention}\n{result}")
            else:
                await ctx.send(result)


async def setup(bot):
    await bot.add_cog(Song(bot))
