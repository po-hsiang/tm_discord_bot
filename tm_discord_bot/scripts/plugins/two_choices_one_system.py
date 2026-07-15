import random


class TwoChoicesOneSystem:
    def __init__(self, candidates_provider):
        # candidates_provider 可為 list，或回傳 list 的 callable（配合延遲載入，
        # 開局當下才取得最新候選清單）
        self.candidates_provider = candidates_provider
        self.is_running = False
        self.stage = 0
        self.round = 0
        self.candidate_index = 0
        self.winners = []
        self.next_winners = []

    def play_or_start_game(self, user_msg):
        if self.is_running:
            return self.__play(user_msg)
        elif user_msg == "!21":
            return self.__start_game()

    def __start_game(self):
        candidates = (
            self.candidates_provider()
            if callable(self.candidates_provider)
            else self.candidates_provider
        )
        if len(candidates) < 16:
            return "候選清單目前不足 16 個（可能資料載入失敗），請稍後再試 🙏"
        self.is_running = True
        self.winners = random.sample(candidates, 16)
        self.stage = len(self.winners).bit_length() - 1
        self.__get_current_candidate()
        return f"總共有 {len(self.winners)} 個候選人！\n" + self.__get_response()

    def __play(self, user_msg):
        winner = self._get_winner(user_msg)
        if winner:
            result = f"你選擇了{winner}\n"
            self.next_winners.append(winner)
            if self.stage >= 2:
                if self.candidate_index < len(self.winners):
                    # 回合中
                    self.__get_current_candidate()
                else:
                    # 同一強最後一回合
                    self.winners = self.next_winners.copy()
                    random.shuffle(self.winners)
                    self.next_winners = []
                    self.stage -= 1
                    self.round = 0
                    self.candidate_index = 0
                    self.__get_current_candidate()
                return result + self.__get_response()
            else:
                if self.candidate_index < len(self.winners):
                    self.__get_current_candidate()
                    return result + self.__get_response()
                else:
                    self.__reset_game()
                    return f"恭喜「{winner}」成為冠軍！"
        else:
            # 這次使用者輸入跟遊戲無關
            return

    def __get_current_candidate(self):
        self.candidate1 = self.winners[self.candidate_index]
        self.candidate2 = self.winners[self.candidate_index + 1]
        self.candidate_index += 2
        self.round += 1

    def _get_winner(self, user_msg):
        if user_msg in ["左", "A", "a"]:
            return self.candidate1
        elif user_msg in ["右", "B", "b"]:
            return self.candidate2
        else:
            return None

    def __get_response(self):
        if self.stage >= 2:
            response = f"{2 ** self.stage} 強淘汰賽 Round {self.round}，請輸入 左(A) 或 右(B)"
        else:
            response = f"總冠軍賽！請輸入左、右選出冠軍！"
        return response + f"\n{self.candidate1} vs {self.candidate2}"

    def __reset_game(self):
        self.is_running = False
        self.round = 0
        self.candidate_index = 0
        self.next_winners = []
