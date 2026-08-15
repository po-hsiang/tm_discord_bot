from tm_bot.services.draw import PullSystem


class AutoReplySystem:
    def __init__(self):
        pull_system = PullSystem()
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
        return ""
