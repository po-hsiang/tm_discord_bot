"""排程執行紀錄：讓每日推播具備「不重複發」與「開機補發」。

一天一則推播就是一筆紀錄，_id 直接用「任務:日期」當天然唯一鍵——
不必額外建唯一索引，也不會有「先查再寫」的競態：插入衝突由資料庫判定。

紀錄的存在即代表「今天這則已經處理完或正在處理」：

* 發送成功         → 留下 status=sent 的紀錄，同一天不會再發第二次
* 內容產不出來／發送失敗 → 刪掉紀錄，讓稍後的開機補發還有機會重試
* 認領後卡住（例如產內容途中容器被重啟）→ 逾 STALE_CLAIM_SECONDS 可被接手

Mongo 不可用時一律「放行」（fail-open）：機器人的本分是把訊息發出去，
寧可承擔極低的重複風險，也不要因為資料庫故障而整天不發。
開機補發是唯一的例外——無法確認就不補（fail-closed），免得每次重啟都洗版。
"""

import logging
from datetime import UTC, datetime, timedelta

from pymongo.errors import DuplicateKeyError, PyMongoError

logger = logging.getLogger(__name__)

COLLECTION_NAME = "schedule_runs"

STATUS_RUNNING = "running"  # 已認領，內容產生中
STATUS_SENT = "sent"  # 已發送完成

# 認領後多久視為「卡住的殘骸」可被接手。內容產生最慢的情況是
# AI 逾時 120 秒兩次、中間還隔 60 秒重試間隔，抓 15 分鐘留足餘裕
STALE_CLAIM_SECONDS = 900

# 紀錄保留天數：留著可稽核「哪天沒發、幾點發的」，過期由 TTL 索引自動清掉，
# 免費方案的空間不必拿來堆歷史
RETENTION_DAYS = 180


def run_id(job_label, day):
    """一則推播的天然唯一鍵：任務名 + 當地日期（例如「早安:2026-08-17」）。"""
    return f"{job_label}:{day.isoformat()}"


class ScheduleRunRepository:
    """schedule_runs 集合的唯一存取點。

    database 為 None 時整組退化為無操作（claim 一律放行），
    呼叫端不需要到處寫 if repo is None。
    """

    def __init__(self, database):
        self._collection = None if database is None else database[COLLECTION_NAME]

    @property
    def enabled(self):
        """是否具備持久化。開機補發只在 True 時才有意義。"""
        return self._collection is not None

    def ensure_indexes(self):
        """建立 TTL 索引；失敗不影響推播（只是舊紀錄不會自動過期）。"""
        if self._collection is None:
            return
        try:
            self._collection.create_index(
                "claimed_at",
                expireAfterSeconds=RETENTION_DAYS * 24 * 60 * 60,
                name="ttl_claimed_at",
            )
        except PyMongoError:
            logger.warning("建立 schedule_runs TTL 索引失敗（不影響推播）", exc_info=True)

    def claim(self, job_label, day, fail_open=True):
        """認領「job_label 在 day 這天」的推播；回傳 True 才可以發送。

        已有 status=sent 的紀錄            → False（今天發過了）
        已有他人剛認領、尚未逾時的紀錄     → False（避免兩個實例同時發）
        認領已逾 STALE_CLAIM_SECONDS       → 接手，回傳 True
        Mongo 不可用                       → 依 fail_open 決定（預設放行）
        """
        if self._collection is None:
            return True

        doc_id = run_id(job_label, day)
        now = datetime.now(UTC)
        try:
            self._collection.insert_one(
                {
                    "_id": doc_id,
                    "job": job_label,
                    "date": day.isoformat(),
                    "status": STATUS_RUNNING,
                    "claimed_at": now,
                }
            )
            return True
        except DuplicateKeyError:
            return self._take_over_stale(doc_id, now)
        except PyMongoError:
            logger.warning(
                "認領%s紀錄失敗（Mongo 不可用），本次%s",
                job_label,
                "照常發送" if fail_open else "略過",
                exc_info=True,
            )
            return fail_open

    def _take_over_stale(self, doc_id, now):
        """接手卡住的認領。條件寫入保證同時間只有一個接手者會成功。"""
        cutoff = now - timedelta(seconds=STALE_CLAIM_SECONDS)
        try:
            taken = self._collection.find_one_and_update(
                {"_id": doc_id, "status": STATUS_RUNNING, "claimed_at": {"$lt": cutoff}},
                {"$set": {"claimed_at": now}},
            )
        except PyMongoError:
            logger.warning("接手排程紀錄失敗：%s", doc_id, exc_info=True)
            return False

        if taken is not None:
            logger.warning("接手卡住的排程紀錄 %s（前次認領後未完成）", doc_id)
        return taken is not None

    def mark_sent(self, job_label, day, chars):
        """標記為已發送；此後同一天的 claim 一律回傳 False。"""
        self._update(
            run_id(job_label, day),
            {"status": STATUS_SENT, "sent_at": datetime.now(UTC), "chars": chars},
        )

    def release(self, job_label, day):
        """放掉認領（這次沒發成）。

        帶 status 條件刪除，確保永遠不會誤刪已完成的紀錄。
        """
        if self._collection is None:
            return
        doc_id = run_id(job_label, day)
        try:
            self._collection.delete_one({"_id": doc_id, "status": STATUS_RUNNING})
        except PyMongoError:
            logger.warning("釋放排程紀錄失敗：%s", doc_id, exc_info=True)

    def _update(self, doc_id, fields):
        if self._collection is None:
            return
        try:
            self._collection.update_one({"_id": doc_id}, {"$set": fields})
        except PyMongoError:
            logger.warning("更新排程紀錄失敗：%s", doc_id, exc_info=True)
