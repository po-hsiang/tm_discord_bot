import random


class TwoChoicesOneSystem:
    def __init__(self, candidates):
        self.candidates = candidates
        self.is_running = False
        self.stage = 0
        self.round = 0
        self.candidate_index = 0
        self.winners = []
        self.next_winners = []

    def start_game(self):
        if self.is_running:
            print("二選一遊戲已經開始了！")
            return
        self.is_running = True
        self.winners = random.sample(self.candidates, 16)
        self.stage = len(self.winners).bit_length() - 1
        self.__get_current_candidate()
        return f"總共有 {len(self.winners)} 個候選人！\n" + self.__get_response()

    def play(self, user_msg):
        winner = self._get_winner(user_msg)
        if winner:
            self.next_winners.append(winner)
            if self.stage >= 2:
                if self.candidate_index < len(self.winners):
                    self.__get_current_candidate()
                    return self.__get_response()
                else:
                    self.winners = self.next_winners.copy()
                    random.shuffle(self.winners)
                    self.next_winners = []
                    self.stage -= 1
                    self.round = 0
                    self.candidate_index = 0
                    self.__get_current_candidate()
                    return self.__get_response()
            else:
                if self.candidate_index < len(self.winners):
                    self.__get_current_candidate()
                    return self.__get_response()
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
        if user_msg in ['左', 'A', 'a']:
            return self.candidate1
        elif user_msg in ['右', 'B', 'b']:
            return self.candidate2
        else:
            return None

    def __get_response(self):
        if self.stage >= 2:
            response = f"{2 ** self.stage} 強淘汰賽 Round {self.round}，請輸入左或右"
        else:
            response = f"總冠軍賽！請輸入左、右選出冠軍！"
        return response + f"\n{self.candidate1} vs {self.candidate2}"

    def __reset_game(self):
        self.is_running = False
        self.round = 0
        self.candidate_index = 0
        self.next_winners = []
