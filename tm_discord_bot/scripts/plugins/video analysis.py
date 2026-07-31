from tm_discord_bot.scripts.plugins.youtube_handler import YouTubeHandler
from tm_discord_bot.scripts.plugins.analyzer import Analyzer


class VideoAnalysis:
    def __init__(self):
        self.youtube_handler = YouTubeHandler()
        self.analyzer = Analyzer()

    def analysis(self, video_url):
        if not self.youtube_handler.is_yt_url(video_url) or not self.youtube_handler.is_youtube_url(video_url):
            print("Bad url")
        video_info = self.youtube_handler.get_video_info_by_url(video_url)


if __name__ == "__main__":
    video_analysis = VideoAnalysis()
    url = "https://youtu.be/QU5CAMmi2EM?si=M_LLYaCnoVrI9zPa"
    video_analysis.analysis(url)
