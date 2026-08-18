"""Google Maps 連結辨識。

刻意不自己解析地點：短網址（`maps.app.goo.gl`）要跟隨轉址才知道指向哪裡，
而長網址裡的地點識別碼並非官方支援的公開格式。解析交給 n8n 端的
Maps Grounding Lite「Resolve Maps URLs」端點——它官方支援短網址，
bot 這邊只負責認出「這是一個 Google 地圖連結」並原樣轉交。
"""

import re
from urllib.parse import urlsplit

# 先粗抓所有網址，再逐一以 host/path 判定；比一條長正規表示式好讀也好測
_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")

# 句尾標點會被貼進網址裡（「…goo.gl/abc。」），比對前先剝掉。
# 刻意不含 ! 與 ?：Maps 長網址的 data 參數本身就大量使用 !
_TRAILING_PUNCTUATION = ".,;:、。，）)]】"

# 允許的地區網域形式：google.com、google.com.tw、google.co.jp…
_GOOGLE_HOST = re.compile(r"(?:www\.)?google\.[a-z.]{2,6}")


# 判斷「訊息是不是只有連結」時可忽略的字元：空白、各種標點與括號。
# 連結外層的 <>、句末的「。」、順手打的驚嘆號都不算「使用者說了話」
_IGNORABLE_CHARS = frozenset(
    " \t\r\n　​<>()[]{}（）〈〉「」『』【】。，、．,.!?！？~～-—_…:：;；\"'"
)


def extract_maps_url(text):
    """回傳文字中第一個 Google 地圖連結；沒有則回傳 None。"""
    for raw in _URL_PATTERN.findall(text or ""):
        url = raw.rstrip(_TRAILING_PUNCTUATION)
        if _is_maps_url(url):
            return url
    return None


def is_bare_link(text, maps_url):
    """訊息扣掉連結之後，只剩空白與標點嗎？

    用來分流兩種意圖：
    * 只貼連結        → 直接回評論摘要卡片（結構化、確定性、附得上來源）
    * 連結旁邊有話    → 交給 AI Agent 對話（它手上也有 maps_review 工具）

    規則刻意做成**確定性**的：不去猜那句話是不是問句。猜錯的代價是
    使用者問了問題卻被回一張卡片（或反之），而且無法解釋為什麼。
    現在的規則一句話就能講完——「只貼連結給你卡片，想聊就多寫一句」。
    """
    remainder = (text or "").replace(maps_url, "", 1)
    return all(char in _IGNORABLE_CHARS for char in remainder)


def _is_maps_url(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path or ""

    # 手機 App「分享」給的就是這種短網址，是實務上最常見的形式
    if host == "maps.app.goo.gl":
        return bool(path.strip("/"))
    # 舊版短網址
    if host == "goo.gl":
        return path.startswith("/maps/")
    # maps.google.com、maps.google.com.tw…
    if host.startswith("maps.google."):
        return True
    # www.google.com/maps/place/…、www.google.com.tw/maps?q=…
    if _GOOGLE_HOST.fullmatch(host):
        return path == "/maps" or path.startswith("/maps/")
    return False
