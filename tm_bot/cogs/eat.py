"""!吃 / !吃啥 / !<分類名> —— 從 Google 試算表隨機抽「今天吃什麼」。

分類名來自試算表，是執行期才知道的動態指令，無法註冊成靜態指令；
因此由 bot 的路由在「找不到對應指令」時呼叫 try_meal()。
"""

from discord.ext import commands


class Eat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def try_meal(self, message):
        """命中分類就抽一個並回覆，回傳是否已處理。"""
        command = message.content.replace("!", "")
        meal = await self.bot.run_blocking(self._pick_meal, command)
        if meal is None:
            return False
        await message.channel.send(f"{message.author.mention} 「{meal}」")
        return True

    def _pick_meal(self, command):
        what_to_eat = self.bot.what_to_eat
        if command in what_to_eat.get_meal_commend_list():
            return what_to_eat.choose_one_meal(command)
        return None


async def setup(bot):
    await bot.add_cog(Eat(bot))
