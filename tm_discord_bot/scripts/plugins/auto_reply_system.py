from .youtube_api import YouTubeAPIHandler
from .pull_system import PullSystem
from .ai_agent_client import AIAgentClient
from .eat_what_system import EatWhatSystem
from .two_choices_one_system import TwoChoicesOneSystem


class AutoReplySystem:
    def __init__(self, yt_song=None, ai_agent=None, what_to_eat=None):
        # 可由外部（main.py）注入共用實例，避免重複建立
        self.yt_song = yt_song if yt_song is not None else YouTubeAPIHandler()
        ai_agent = ai_agent if ai_agent is not None else AIAgentClient()
        what_to_eat = what_to_eat if what_to_eat is not None else EatWhatSystem()
        pull_system = PullSystem()
        self.two_choice_game = TwoChoicesOneSystem(what_to_eat.get_total_answers_list)
        self.song_command_list = ["!聽", "!歌", "!聽歌", "!listen", "!song"]
        # AI 指令清單：main.py 據此把這些指令分派到 AI 專用執行緒池
        # （agent 帶工具可能跑數十秒，不能佔住原生指令的單一 worker）
        self.ai_command_list = ["!問", "!gpt"]
        self.str_command = {
            "!心結": "沒有心結啦！哪次心結了？\n然後新垣結衣已婚QQ",
        }
        self.func_command = {
            "!抽": pull_system.pull_a_sticks,
            "!問": ai_agent.ask,
            "!gpt": ai_agent.ask,
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
