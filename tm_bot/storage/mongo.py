"""MongoDB 連線層：只負責「怎麼連上、連不上怎麼辦」，不含任何業務語意。

同一個 Atlas 叢集裡還有 Twitch Bot 專用的 tm_twitch_bot，本專案不得存取。
三道防線互相獨立，任何一道單獨失效都還擋得住：

1. Atlas 端：連線帳號的權限僅 readWrite @ tm_discord_bot，越權由伺服器直接拒絕。
2. 本模組：資料庫名稱命中黑名單就拒絕啟動——設定填錯會當場炸給人看，不會靜默連過去。
3. 設定端：資料庫名稱一律由 MONGODB_DB 明確指定，不從連線字串的路徑段推斷。

除了上述設定錯誤之外，連不上一律降級（回傳 None）而非中止：
持久化是加分功能，不該因為 Atlas 免費方案打個噴嚏就讓整隻機器人下線。
"""

import logging

from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# 同叢集中不屬於本專案的資料庫，任何情況下都不得連上
FORBIDDEN_DB_NAMES = frozenset({"tm_twitch_bot"})

# Atlas 免費方案（M0）反應本來就慢，但排程一天只用得到它幾次，
# 逾時寧可設短：連不上就儘快降級，不要讓呼叫端空等
SERVER_SELECTION_TIMEOUT_MS = 5_000
CONNECT_TIMEOUT_MS = 5_000
SOCKET_TIMEOUT_MS = 10_000


class ForbiddenDatabaseError(RuntimeError):
    """設定指向了不屬於本專案的資料庫。"""


def create_database(uri, db_name):
    """建立連線並回傳 pymongo Database；未設定時回傳 None（持久化功能停用）。

    此處只建立連線物件（pymongo 內部惰性連線，不會阻塞），
    實際連通性交由 ping() 在啟動時驗證。
    """
    if not uri or not db_name:
        logger.info("未設定 MONGODB_URI／MONGODB_DB，持久化功能停用（其餘功能不受影響）")
        return None

    if db_name in FORBIDDEN_DB_NAMES:
        raise ForbiddenDatabaseError(
            f"MONGODB_DB 不得為「{db_name}」：該資料庫屬於 Twitch Bot，本專案不得存取。"
            "請將 .env 的 MONGODB_DB 改回本專案專屬的資料庫名稱。"
        )

    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=CONNECT_TIMEOUT_MS,
        socketTimeoutMS=SOCKET_TIMEOUT_MS,
        # 讀回的時間欄位帶 UTC 時區，避免與 aware 時間相比時拋 TypeError
        tz_aware=True,
        # 讓 Atlas 的連線監控看得出來是誰連的，日後排查比較好認
        appname="tm_discord_bot",
    )
    return client[db_name]


def ping(database):
    """驗證連線是否真的通；連不上只記錄警告並回傳 False，不中止啟動。

    刻意 ping 目標資料庫而非 admin：本專案的帳號權限只涵蓋自己的資料庫，
    對 admin 下指令不是每種權限設定都會過。
    """
    if database is None:
        return False
    try:
        database.command("ping")
    except PyMongoError as exc:
        logger.warning("MongoDB 連線失敗（資料庫 %s），持久化功能降級：%s", database.name, exc)
        return False
    logger.info("MongoDB 已連線（資料庫：%s）", database.name)
    return True
