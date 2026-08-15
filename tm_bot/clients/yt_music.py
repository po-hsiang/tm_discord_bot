import logging

import requests

logger = logging.getLogger(__name__)

LOAD_FAIL_MESSAGE = "歌單服務暫時連不上線，請稍後再試 🙏"


class SongPicker:
    """yt-music-mcp 歌單微服務的 HTTP 客戶端。

    歌單載入、快取（TTL 6 小時）、失敗重試與 API 配額都在伺服器端處理，
    機器人不再需要 YouTube API Key，也不用在本地維護歌單快取。
    """

    TIMEOUT = (3, 30)  # (連線, 讀取)；跨歌單搜尋冷啟動可能較久

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def choose_one_song(self, keyword=""):
        params = {"count": 1}
        if keyword:
            params["q"] = keyword
        try:
            resp = requests.get(f"{self.base_url}/random", params=params, timeout=self.TIMEOUT)
            resp.raise_for_status()
            songs = resp.json()["songs"]
        except requests.RequestException as e:
            logger.warning("取歌失敗，之後使用時會再重試：%s", e)
            return LOAD_FAIL_MESSAGE
        return songs[0]["url"] if songs else LOAD_FAIL_MESSAGE

    def search_keyword_in_song_list(self, keyword):
        if len(keyword) < 2:
            return ["搜尋請大於等於2個字"]
        try:
            resp = requests.get(
                f"{self.base_url}/search", params={"q": keyword}, timeout=self.TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.warning("搜尋歌單失敗：%s", e)
            return [LOAD_FAIL_MESSAGE]

        results = data.get("results") or []
        if not results:
            return []
        answer = self.__generate_song_list_response(results)
        total = data.get("total_matches", len(results))
        answer[0] = f"歌單內標題含有「{keyword}」的歌共有{total}首：\n" + answer[0]
        return answer

    def __generate_song_list_response(self, songs):
        # 與 Discord 2000 字上限相容：每段訊息控制在 1900 字內
        result = ""
        answer = []
        for index, song in enumerate(songs):
            current_song = (
                f"{index + 1}.《{song['channel']}》{song['title']}〔{song['playlist']}〕\n"
            )
            if len(result) + len(current_song) >= 1900:
                answer.append(result)
                result = ""
            result += current_song
        if result:
            answer.append(result)
        return answer
