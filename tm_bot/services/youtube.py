"""YouTube 連結解析（純函式，不依賴 Discord 也不做任何 I/O）。"""

import re

# 支援的三種 YouTube 連結格式（影片 ID 固定 11 碼；/shorts/ 短影片不在此功能範圍）
_VIDEO_ID_PATTERNS = (
    re.compile(r"youtube\.com/watch\?(?:[^\s]*&)?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"youtube\.com/live/([A-Za-z0-9_-]{11})"),
)


def extract_video_id(text):
    """從訊息文字取出第一個 YouTube 影片 ID；沒有影片連結時回傳 None。"""
    for pattern in _VIDEO_ID_PATTERNS:
        matched = pattern.search(text or "")
        if matched:
            return matched.group(1)
    return None
