import random


def pull_a_sticks():
    black = "<:tmStaringBlack:1049667815168286751>"
    yellow = "<:tmStaring:1000029916953333760>"
    rainbow = "<:tmStaringRainbow:1049668332766367804>"
    luck_sticks = [black, yellow, rainbow]
    weights = [94.3, 5.1, 0.6]
    results = random.choices(luck_sticks, weights=weights, k=10)
    if yellow not in results or rainbow not in results:
        results.pop()
        results.append(yellow)
    return ' '.join(results)


if __name__ == "__main__":
    print(pull_a_sticks())
