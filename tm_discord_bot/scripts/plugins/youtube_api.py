from googleapiclient.discovery import build
from config_utils import read_config_file
import random

CONFIG = read_config_file()


class YouTubeAPIHandler:
    def __init__(self):
        api_key = CONFIG.get("youtube_developer_key")

        youtube = build("youtube", "v3", developerKey=api_key)

        playlist_id = CONFIG.get("my_yt_music_playlist_id")

        videos = []

        next_page_token = None
        while True:
            pl_request = youtube.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            pl_response = pl_request.execute()
            vid_ids = []
            for item in pl_response["items"]:
                vid_ids.append(item["contentDetails"]["videoId"])

            vid_request = youtube.videos().list(
                part="snippet,statistics", id=",".join(vid_ids)
            )
            vid_response = vid_request.execute()
            for item in vid_response["items"]:
                vid_views = item["statistics"]["viewCount"]
                vid_id = item["id"]
                yt_link = f"https://youtu.be/{vid_id}"
                "https://youtu.be/wVwcOq-SsiU"
                videos.append(
                    {
                        "views": int(vid_views),
                        "url": yt_link,
                        "title": item["snippet"]["title"],
                    }
                )
            next_page_token = pl_response.get("nextPageToken")
            if not next_page_token:
                break

        videos.sort(key=lambda vid: vid["views"], reverse=True)

        # for index, video in enumerate(videos):
        #     print(f"{index + 1} video: {video['url']}, views: {video['views']}, 歌名: {video['title']}")
        # print(f"total: {len(videos)}")

        self.song_list = videos

    def choose_one_song(self):
        song = random.choice(self.song_list)
        return song["url"]

    def check_song_title(self, check_song_title):
        print(f"check_song_title: {check_song_title}")
        if len(check_song_title) < 2:
            return f"搜尋請大於等於2個字"

        have_checked = False
        count = 0

        result = ""
        for song in self.song_list:
            if check_song_title in song["title"]:
                have_checked = True
                count += 1
                result += f"{count}. {song['title']}\n"

        if have_checked:
            return f"虎喵歌單內標題含有「{check_song_title}」的歌共有{count}首：\n" + result
        else:
            return f"虎喵歌單內的歌標題都沒有「{check_song_title}」字元"
