import asyncio
import logging
import random

import discord

logger = logging.getLogger(__name__)

# 賽制參數：8 強（共 7 輪）、每輪 30 秒（主人於測試頻道試玩後定案）
BRACKET_SIZE = 8
ROUND_SECONDS = 30

START_COMMAND = "!投票賽"

NOT_ENOUGH_MESSAGE = (
    f"候選清單目前不足 {BRACKET_SIZE} 個（可能資料載入失敗），請稍後再試 🙏"
)
ALREADY_RUNNING_MESSAGE = "已經有一場投票淘汰賽進行中囉！等這場打完再開新的 🏟️"


def tally_votes(votes):
    """votes：{user_id: "left"/"right"} → (左票數, 右票數)。"""
    left = sum(1 for choice in votes.values() if choice == "left")
    return left, len(votes) - left


def decide_winner(left, right, left_votes, right_votes):
    """回傳 (晉級者, 是否由運氣決定)；平手或無人投票時隨機晉級。"""
    if left_votes > right_votes:
        return left, False
    if right_votes > left_votes:
        return right, False
    return random.choice([left, right]), True


def stage_name(remaining):
    return "總冠軍賽" if remaining == 2 else f"{remaining} 強"


class _RoundView(discord.ui.View):
    """單一輪次的投票 UI：兩顆按鈕、每人一票、時間內可改票。"""

    def __init__(self, left, right):
        super().__init__(timeout=ROUND_SECONDS)
        self.votes = {}
        for side, label, style in (
            ("left", left, discord.ButtonStyle.primary),
            ("right", right, discord.ButtonStyle.success),
        ):
            # Discord 按鈕 label 上限 80 字元
            button = discord.ui.Button(label=label[:80], style=style)
            button.callback = self._make_callback(side, label)
            self.add_item(button)

    def _make_callback(self, side, label):
        async def callback(interaction):
            previous = self.votes.get(interaction.user.id)
            self.votes[interaction.user.id] = side
            note = "（已幫你改票）" if previous and previous != side else ""
            # ephemeral：投票結果只有本人看得到，開票前保持懸念
            await interaction.response.send_message(
                f"你投給了「{label}」{note}", ephemeral=True
            )

        return callback

    def disable_all(self):
        for item in self.children:
            item.disabled = True


class VoteTournament:
    """按鈕投票淘汰賽：全頻道按按鈕投票，每輪時間到最高票晉級。

    與 `!21` 打字版淘汰賽（two_choices_one_system）並存，互不影響；
    候選來源同樣是「吃什麼」清單。一次只允許一場（is_running 守門）。
    """

    def __init__(self, candidates_provider):
        # candidates_provider：回傳候選 list 的 callable（配合延遲載入）
        self.candidates_provider = candidates_provider
        self.is_running = False

    async def start(self, channel, loop, executor):
        if self.is_running:
            await channel.send(ALREADY_RUNNING_MESSAGE)
            return
        self.is_running = True
        try:
            # 候選清單可能觸發 Google Sheets 載入（阻塞），移到 worker 執行緒
            candidates = await loop.run_in_executor(executor, self.candidates_provider)
            if len(candidates) < BRACKET_SIZE:
                await channel.send(NOT_ENOUGH_MESSAGE)
                return
            await self._run_bracket(channel, random.sample(candidates, BRACKET_SIZE))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("投票淘汰賽發生錯誤，本場中止")
            await channel.send("投票淘汰賽出了點狀況，本場先中止，請再開一場 🙏")
        finally:
            self.is_running = False

    async def _run_bracket(self, channel, contenders):
        await channel.send(
            f"🏟️ **{BRACKET_SIZE} 強按鈕投票淘汰賽開打！**\n"
            f"每輪 {ROUND_SECONDS} 秒，大家一起按按鈕投票，最高票晉級（可改票、開票前保密）！"
        )
        while len(contenders) > 1:
            winners = []
            for i in range(0, len(contenders), 2):
                winners.append(
                    await self._run_round(
                        channel, stage_name(len(contenders)), contenders[i], contenders[i + 1]
                    )
                )
            random.shuffle(winners)
            contenders = winners
        await channel.send(f"👑 冠軍出爐：「{contenders[0]}」！感謝各位好虎粉熱情參與～")

    async def _run_round(self, channel, stage, left, right):
        view = _RoundView(left, right)
        message = await channel.send(f"**{stage}**：「{left}」 vs 「{right}」", view=view)
        await view.wait()  # 等到本輪時間截止（view timeout）
        view.disable_all()
        try:
            await message.edit(view=view)  # 時間到就鎖按鈕
        except discord.HTTPException:
            pass  # 鎖不上（如訊息被刪）不影響賽程
        left_votes, right_votes = tally_votes(view.votes)
        winner, by_luck = decide_winner(left, right, left_votes, right_votes)
        suffix = "（平手，貓咪擲硬幣決定 🪙）" if by_luck else ""
        await channel.send(
            f"開票：「{left}」{left_votes} 票 vs 「{right}」{right_votes} 票"
            f" → **「{winner}」晉級！**{suffix}"
        )
        return winner
