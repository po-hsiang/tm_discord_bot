import unittest
from datetime import UTC, date, datetime, timedelta

from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from tm_bot.storage.mongo import ForbiddenDatabaseError, create_database, ping
from tm_bot.storage.schedule_runs import (
    STALE_CLAIM_SECONDS,
    STATUS_RUNNING,
    STATUS_SENT,
    ScheduleRunRepository,
    run_id,
)

DAY = date(2026, 8, 17)
LABEL = "早安"
DOC_ID = "早安:2026-08-17"


class FakeCollection:
    """夠用的記憶體版集合：只實作 repository 真正呼叫到的那幾個方法。"""

    def __init__(self, error=None):
        self.docs = {}
        self.error = error
        self.indexes = []

    def _maybe_fail(self):
        if self.error is not None:
            raise self.error

    def insert_one(self, doc):
        self._maybe_fail()
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("duplicate key")
        self.docs[doc["_id"]] = dict(doc)

    def find_one_and_update(self, criteria, update):
        self._maybe_fail()
        doc = self.docs.get(criteria["_id"])
        if doc is None or doc["status"] != criteria["status"]:
            return None
        if doc["claimed_at"] >= criteria["claimed_at"]["$lt"]:
            return None
        before = dict(doc)
        doc.update(update["$set"])
        return before

    def update_one(self, criteria, update):
        self._maybe_fail()
        doc = self.docs.get(criteria["_id"])
        if doc is not None:
            doc.update(update["$set"])

    def delete_one(self, criteria):
        self._maybe_fail()
        doc = self.docs.get(criteria["_id"])
        if doc is not None and doc["status"] == criteria["status"]:
            del self.docs[criteria["_id"]]

    def create_index(self, key, **options):
        self._maybe_fail()
        self.indexes.append((key, options))


class FakeDatabase:
    def __init__(self, collection, name="tm_discord_bot"):
        self.collection = collection
        self.name = name
        self.commands = []
        self.command_error = None

    def __getitem__(self, _name):
        return self.collection

    def command(self, name):
        if self.command_error is not None:
            raise self.command_error
        self.commands.append(name)
        return {"ok": 1}


def make_repo(error=None):
    collection = FakeCollection(error)
    return ScheduleRunRepository(FakeDatabase(collection)), collection


def aged(seconds):
    """回傳一個「幾秒前」的 UTC 時間。"""
    return datetime.now(UTC) - timedelta(seconds=seconds)


class TestCreateDatabase(unittest.TestCase):
    def test_missing_settings_disables_storage(self):
        self.assertIsNone(create_database("", "tm_discord_bot"))
        self.assertIsNone(create_database("mongodb+srv://x/", ""))

    def test_twitch_bot_database_is_refused(self):
        # 這是保護 Twitch Bot 資料庫的第二道防線：設定填錯要當場炸掉，不能靜默連過去
        with self.assertRaises(ForbiddenDatabaseError) as caught:
            create_database("mongodb+srv://user:pw@cluster0.example.mongodb.net/", "tm_twitch_bot")
        self.assertIn("tm_twitch_bot", str(caught.exception))


class TestPing(unittest.TestCase):
    def test_none_database_is_not_reachable(self):
        self.assertFalse(ping(None))

    def test_reachable_database_returns_true(self):
        database = FakeDatabase(FakeCollection())
        self.assertTrue(ping(database))
        self.assertEqual(database.commands, ["ping"])

    def test_unreachable_database_degrades_instead_of_raising(self):
        database = FakeDatabase(FakeCollection())
        database.command_error = ServerSelectionTimeoutError("no primary")
        self.assertFalse(ping(database))


class TestRunId(unittest.TestCase):
    def test_key_is_job_and_local_date(self):
        self.assertEqual(run_id(LABEL, DAY), DOC_ID)


class TestDisabledRepository(unittest.TestCase):
    """沒有 MongoDB 時整組退化為無操作，且一律放行。"""

    def setUp(self):
        self.repo = ScheduleRunRepository(None)

    def test_reports_disabled(self):
        self.assertFalse(self.repo.enabled)

    def test_claim_always_allows_sending(self):
        self.assertTrue(self.repo.claim(LABEL, DAY))
        self.assertTrue(self.repo.claim(LABEL, DAY))  # 第二次也放行，因為沒地方記

    def test_other_operations_are_noops(self):
        self.repo.ensure_indexes()
        self.repo.mark_sent(LABEL, DAY, 100)
        self.repo.release(LABEL, DAY)


class TestClaim(unittest.TestCase):
    def test_first_claim_succeeds_and_records_running(self):
        repo, collection = make_repo()

        self.assertTrue(repo.claim(LABEL, DAY))

        doc = collection.docs[DOC_ID]
        self.assertEqual(doc["status"], STATUS_RUNNING)
        self.assertEqual(doc["job"], LABEL)
        self.assertEqual(doc["date"], "2026-08-17")

    def test_second_claim_is_refused_while_first_is_fresh(self):
        repo, _ = make_repo()
        repo.claim(LABEL, DAY)

        self.assertFalse(repo.claim(LABEL, DAY))

    def test_claim_is_refused_after_successful_send(self):
        # 核心的冪等保證：今天發過了就不會再發第二次
        repo, _ = make_repo()
        repo.claim(LABEL, DAY)
        repo.mark_sent(LABEL, DAY, 120)

        self.assertFalse(repo.claim(LABEL, DAY))

    def test_stale_claim_can_be_taken_over(self):
        # 上次認領後容器就被砍掉，紀錄卡在 running：逾時後要能接手，否則那天永遠發不出去
        repo, collection = make_repo()
        repo.claim(LABEL, DAY)
        collection.docs[DOC_ID]["claimed_at"] = aged(STALE_CLAIM_SECONDS + 60)

        self.assertTrue(repo.claim(LABEL, DAY))

    def test_stale_takeover_does_not_apply_to_sent_records(self):
        repo, collection = make_repo()
        repo.claim(LABEL, DAY)
        repo.mark_sent(LABEL, DAY, 120)
        collection.docs[DOC_ID]["claimed_at"] = aged(STALE_CLAIM_SECONDS + 60)

        self.assertFalse(repo.claim(LABEL, DAY))

    def test_mongo_failure_defaults_to_fail_open(self):
        # 資料庫故障時寧可冒重複的風險也要把訊息發出去
        repo, _ = make_repo(ServerSelectionTimeoutError("no primary"))

        self.assertTrue(repo.claim(LABEL, DAY))

    def test_mongo_failure_can_fail_closed(self):
        # 開機補發用 fail_open=False：無法確認就不補，免得每次重啟都洗版
        repo, _ = make_repo(ServerSelectionTimeoutError("no primary"))

        self.assertFalse(repo.claim(LABEL, DAY, fail_open=False))


class TestMarkSentAndRelease(unittest.TestCase):
    def test_mark_sent_records_status_and_length(self):
        repo, collection = make_repo()
        repo.claim(LABEL, DAY)

        repo.mark_sent(LABEL, DAY, 137)

        doc = collection.docs[DOC_ID]
        self.assertEqual(doc["status"], STATUS_SENT)
        self.assertEqual(doc["chars"], 137)
        self.assertIn("sent_at", doc)

    def test_release_removes_the_claim_so_catch_up_can_retry(self):
        repo, collection = make_repo()
        repo.claim(LABEL, DAY)

        repo.release(LABEL, DAY)

        self.assertNotIn(DOC_ID, collection.docs)
        self.assertTrue(repo.claim(LABEL, DAY))  # 可再次認領

    def test_release_never_deletes_a_successful_record(self):
        repo, collection = make_repo()
        repo.claim(LABEL, DAY)
        repo.mark_sent(LABEL, DAY, 100)

        repo.release(LABEL, DAY)

        self.assertEqual(collection.docs[DOC_ID]["status"], STATUS_SENT)

    def test_mongo_failure_during_bookkeeping_is_swallowed(self):
        # 訊息已經發出去了，事後記帳失敗不該把例外丟回排程迴圈
        repo, _ = make_repo(ServerSelectionTimeoutError("no primary"))
        repo.mark_sent(LABEL, DAY, 100)
        repo.release(LABEL, DAY)


class TestEnsureIndexes(unittest.TestCase):
    def test_creates_ttl_index_on_claimed_at(self):
        repo, collection = make_repo()

        repo.ensure_indexes()

        key, options = collection.indexes[0]
        self.assertEqual(key, "claimed_at")
        self.assertGreater(options["expireAfterSeconds"], 0)

    def test_index_failure_does_not_raise(self):
        repo, _ = make_repo(ServerSelectionTimeoutError("no primary"))
        repo.ensure_indexes()


if __name__ == "__main__":
    unittest.main()
