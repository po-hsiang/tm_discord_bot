from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled
from youtube_transcript_api.formatters import SRTFormatter
from tm_discord_bot.utils.config_utils import config
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import requests
import os
import re


class YouTubeHandler:
    def __init__(self):
        self.API_KEY = os.getenv("YOUTUBE_API_KEY")
        if not self.API_KEY:
            raise RuntimeError("環境變數 YOUTUBE_API_KEY 未設定，請於專案根目錄建立 .env（格式參考 .env.example）")
        self.VIDEO_API_URL = config["youtube"]["api_url"].format(route="videos")
        self.DOWNLOAD_FOLDER = Path.home() / config["youtube"]["download_folder"]
        self.MP3_LIMIT_SIZE = int(config["youtube"]["mp3_limit_size"])

    def get_video_info_by_url(self, url):
        return self.get_video_info_by_id(self.get_video_id(url))

    def get_video_info_by_id(self, video_id):
        stats_params = self._build_params(video_id)
        video_result = self._get_data_by_api(self.VIDEO_API_URL, stats_params)
        return self._process_response(video_result)

    def _build_params(self, video_id):
        return {
            "key": self.API_KEY,
            "id": video_id,
            "part": "snippet,statistics,contentDetails",
        }

    def _get_data_by_api(self, url, params):
        response = requests.get(url, params=params)
        return response.json()

    def _process_response(self, video_result):
        result = []
        if "items" in video_result and video_result["items"]:
            for index, item in enumerate(video_result["items"]):
                info = VideoInfo(
                    video_id=item["id"],
                    video_url=f"https://youtu.be/{item['id']}",
                    title=item["snippet"].get("title"),
                    channel_title=item["snippet"].get("channelTitle"),
                    published_at=self._convert_str_to_datetime(item["snippet"].get("publishedAt")),
                    thumbnails_default_url=self._get_thumbnails_url(item["snippet"]["thumbnails"]),
                )
                if "statistics" in item.keys():
                    info.view_count = item["statistics"].get("viewCount")
                    info.like_count = item["statistics"].get("likeCount")
                    info.comment_count = item["statistics"].get("commentCount")
                if "contentDetails" in item.keys():
                    info.duration, duration_secs = self._parse_duration(item["contentDetails"].get("duration"))
                    info.estimated_execution_time = self.get_estimated_execution_time(duration_secs)

                ################################
                # print(f"\n{index + 1}.\n影片標題: {info.title}")
                # print(f"頻道: {info.channel_title}")
                # print(f"觀看數: {info.view_count}, 喜歡數: {info.like_count}, 發佈時間: {info.published_at}")
                # print(f"連結: {info.video_url}")
                # print(f"影片時長: {info.duration}, 總共幾秒: {info.duration.seconds}")
                # print(f"item['contentDetails'].get('contentRating'): {item['contentDetails'].get('contentRating')}")
                ################################
                result.append(info.dict())
        else:
            return {"error": "Video not found or access denied."}

        return result[0] if len(result) == 1 else result

    @staticmethod
    def is_yt_url(url):
        try:
            result = urlparse(url)
            return bool(result.scheme)
        except ValueError:
            return False

    @staticmethod
    def is_youtube_url(url):
        return "youtube.com" in url or "youtu.be" in url

    @staticmethod
    def get_video_id(video_string):
        parsed_url = urlparse(video_string)
        params = parse_qs(parsed_url.query)
        video_id = None

        if "https://www.youtube.com/live/" in video_string or "youtu.be" in parsed_url.netloc:
            # video_id = os.path.split(parsed_url.path)[1]
            video_id = Path(parsed_url.path).name
        elif "v" in params:
            video_id = params.get("v", [""])[0]

        if video_id:
            return video_id
        raise Exception("Invalid url")

    def get_subtitle(self, video_info):
        self.video_info = video_info
        srt_subtitle = self.youtube_cc_subtitle()
        if srt_subtitle is None:
            srt_subtitle = self.youtube_subtitle()
            if isinstance(srt_subtitle, str):
                return srt_subtitle, None

        subtitle = " ".join([s[1] for s in srt_subtitle])
        return srt_subtitle, subtitle

    def youtube_cc_subtitle(self):
        title = self.video_info["title"]
        transcript = self.get_cc_subtitle()
        if transcript is None:
            return None

        formatter = SRTFormatter()
        srt_formatted = formatter.format_transcript(transcript)
        result = re.findall("(\d+:\d+:\d+,\d+ --> \d+:\d+:\d+,\d+)\s+(.+)", srt_formatted)
        result.insert(0, ("00:00:00,000 --> 00:00:00,000", title))
        return result

    def get_cc_subtitle(self):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_info["video_id"])
        except TranscriptsDisabled:
            return None

        language_code = ["zh-Hant-TW", "zh-Hant", "zh-TW", "en"]
        transcript = None
        script_list = [script for script in transcript_list]
        for code in language_code:
            for script in script_list:
                if code == script.language_code and script.is_generated is False:
                    transcript = script.fetch()
                    break

        if transcript is None:
            for script in script_list:
                if script.is_generated is False:
                    transcript = script.fetch()
                    break

        return transcript