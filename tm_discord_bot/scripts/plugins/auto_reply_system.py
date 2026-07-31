from .pull_system import PullSystem
from .eat_what_system import EatWhatSystem
from .two_choices_one_system import TwoChoicesOneSystem


class AutoReplySystem:
    def __init__(self, what_to_eat=None):
        # 可由外部（main.py）注入共用實例，避免重複建立
        what_to_eat = what_to_eat if what_to_eat is not None else EatWhatSystem()
        pull_system = PullSystem()
        self.two_choice_game = TwoChoicesOneSystem(what_to_eat.get_total_answers_list)
        self.str_command = {
            "!心結": "沒有心結啦！哪次心結了？\n然後新垣結衣已婚QQ",
            # 舊 AI 指令的轉換提示（頻道已支援自然語言直接對話）
            "!問": "現在不用指令囉！直接把想說的話打出來，我就會回覆你 ✨",
            "!gpt": "現在不用指令囉！直接把想說的話打出來，我就會回覆你 ✨",
        }
        self.func_command = {
            "!抽": pull_system.pull_a_sticks,
        }

    def get_reply(self, msg, *args, **kwargs):
        msg_split = msg.split(" ", 1)
        cmd = msg_split[0]
        if len(msg_split) > 1:
            question = msg_split[1]
            kwargs["question"] = question

        if cmd in self.str_command:
            return self.str_command[cmd]
        elif cmd in self.func_command:
            func = self.func_command[cmd]
            if callable(func):
                return func(*args, **kwargs)
        else:
            return self.two_choice_game.play_or_start_game(msg)
        return ""
