import sys
import unittest
from pathlib import Path
from unittest import mock

# vote_tournament 內部以 scripts/ 為根匯入，需先加入 sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "tm_discord_bot" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugins.vote_tournament import (  # noqa: E402
    decide_winner,
    stage_name,
    tally_votes,
)


class TestTallyVotes(unittest.TestCase):
    def test_empty_votes(self):
        self.assertEqual(tally_votes({}), (0, 0))

    def test_counts_each_side(self):
        votes = {1: "left", 2: "right", 3: "left", 4: "left"}
        self.assertEqual(tally_votes(votes), (3, 1))

    def test_changed_vote_counts_once(self):
        # 同一人改票：dict 以 user_id 為鍵，天然一人一票
        votes = {}
        votes[42] = "left"
        votes[42] = "right"
        self.assertEqual(tally_votes(votes), (0, 1))


class TestDecideWinner(unittest.TestCase):
    def test_left_majority_wins(self):
        self.assertEqual(decide_winner("滷肉飯", "牛肉麵", 3, 1), ("滷肉飯", False))

    def test_right_majority_wins(self):
        self.assertEqual(decide_winner("滷肉飯", "牛肉麵", 1, 3), ("牛肉麵", False))

    def test_tie_is_decided_by_luck(self):
        with mock.patch("plugins.vote_tournament.random.choice", return_value="牛肉麵"):
            winner, by_luck = decide_winner("滷肉飯", "牛肉麵", 2, 2)
        self.assertEqual(winner, "牛肉麵")
        self.assertTrue(by_luck)

    def test_no_votes_is_decided_by_luck(self):
        winner, by_luck = decide_winner("滷肉飯", "牛肉麵", 0, 0)
        self.assertIn(winner, ("滷肉飯", "牛肉麵"))
        self.assertTrue(by_luck)


class TestStageName(unittest.TestCase):
    def test_final_round(self):
        self.assertEqual(stage_name(2), "總冠軍賽")

    def test_earlier_rounds(self):
        self.assertEqual(stage_name(8), "8 強")
        self.assertEqual(stage_name(4), "4 強")


if __name__ == "__main__":
    unittest.main()
