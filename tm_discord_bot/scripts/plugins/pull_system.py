import random


class PullSystem:
    def __init__(self):
        self.black = "<:tmStaringBlack:1049667815168286751>"
        self.yellow = "<:tmStaring:1000029916953333760>"
        self.rainbow = "<:tmStaringRainbow:1049668332766367804>"
        self.luck_sticks = [self.black, self.yellow, self.rainbow]
        self.weights = [94.3, 5.1, 0.6]

    def pull_a_sticks(self, *args, **kwargs):
        # 接受並忽略多餘參數：「!抽 xxx」帶了參數也不會 TypeError 已讀不回
        results = random.choices(self.luck_sticks, weights=self.weights, k=10)
        results = self.__guaranteed_mechanism(results)
        return " ".join(results)

    def __guaranteed_mechanism(self, results):
        if self.yellow not in results and self.rainbow not in results:
            results.pop()
            results.append(self.yellow)
        return results
