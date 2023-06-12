from googleapiclient.discovery import build
from config_utils import read_config_file
import random

CONFIG = read_config_file()


class YouTubeAPIHandler:
    def __init__(self):
        self.song_list = self.__sort_yt_playlist()

    def __sort_yt_playlist(self):
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
                        "channel": item["snippet"]["channelTitle"],
                    }
                )
            next_page_token = pl_response.get("nextPageToken")
            if not next_page_token:
                break

        videos.sort(key=lambda vid: vid["views"], reverse=True)
        return videos

    def choose_one_song(self):
        song = random.choice(self.song_list)
        return song["url"]

    def search_keyword_in_song_list(self, keyword):
        if len(keyword) < 2:
            return [f"搜尋請大於等於2個字"]
        matched_songs = [
            song for song in self.song_list if self.__is_keyword_matched(song, keyword)
        ]
        count = len(matched_songs)
        answer = self.__generate_song_list_response(matched_songs)
        return self.__generate_search_result_message(keyword, count, answer)

    def __is_keyword_matched(self, song, keyword):
        title = song["title"].lower()
        channel = song["channel"].lower()
        keyword = keyword.lower()
        return keyword in title or keyword in channel

    def __generate_song_list_response(self, songs):
        result = ""
        answer = []
        for index, song in enumerate(songs):
            current_song = f"{index + 1}.《{song['channel']}》{song['title']}\n"
            temp_result = result + current_song
            if len(temp_result) >= 1900:
                answer.append(result)
                result = ""
            result += current_song
        if result:
            answer.append(result)
        return answer

    def __generate_search_result_message(self, keyword, count, answer):
        if answer:
            answer[0] = f"歌單內標題含有「{keyword}」的歌共有{count}首：\n" + answer[0]
        return answer
