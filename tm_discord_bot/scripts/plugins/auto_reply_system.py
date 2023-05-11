from youtube_api import YouTubeAPIHandler
from pull_system import pull_a_sticks


class AutoReplySystem():
    def __init__(self):
        self.yt_song = YouTubeAPIHandler()
        self.song_command_list = ["!聽", "!歌", "!聽歌", "!listen", "!song"]
        self.str_command = {
            "!心結": "沒有心結啦！哪次心結了？",
            "!新垣結衣": "她已婚",
        }
        self.func_command = {
            "!抽": pull_a_sticks
        }

    def get_reply(self, msg_content):
        if msg_content in self.str_command:
            return self.str_command[msg_content]
        elif msg_content in self.func_command:
            return self.func_command[msg_content]()
        elif msg_content in self.song_command_list:
            song = self.yt_song.choose_one_song()
            return f"從虎喵的歌單內隨機挑了這首歌給你 \n {song}"
