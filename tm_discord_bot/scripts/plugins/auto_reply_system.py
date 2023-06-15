from .youtube_api import YouTubeAPIHandler
from .pull_system import PullSystem
from .openai_api import OpenaiAPI
from .eat_what_system import EatWhatSystem
from .two_choices_one_system import TwoChoicesOneSystem


class AutoReplySystem:
    def __init__(self):
        self.yt_song = YouTubeAPIHandler()
        pull_system = PullSystem()
        chat_gpt = OpenaiAPI()
        what_to_eat = EatWhatSystem()
        self.two_choice_game = TwoChoicesOneSystem(what_to_eat.total_answers_list)
        self.song_command_list = ["!聽", "!歌", "!聽歌", "!listen", "!song"]
        self.str_command = {
            "!心結": "沒有心結啦！哪次心結了？\n然後新垣結衣已婚QQ",
        }
        self.func_command = {
            "!抽": pull_system.pull_a_sticks,
            "!問": chat_gpt.ask_question,
            "!gpt": chat_gpt.ask_question,
            "!搜圖": chat_gpt.search_keyword_image,
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
