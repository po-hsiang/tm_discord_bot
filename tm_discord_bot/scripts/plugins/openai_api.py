from config_utils import read_config_file
import openai
import time

CONFIG = read_config_file()
openai.api_key = CONFIG.get("openai_api_key")

API_FAIL_MESSAGE = "無法成功打 API，已達到最大重試次數，快看看 Log"


class OpenaiAPI:
    def __init__(self):
        self.model = CONFIG.get("openai_model")
        self.token_limit = self.__get_token_limit()
        self.system_role = {
            "role": "system",
            "content": f"""# 妳是帥氣幽默的遊戲男實況主「老虎喵喵喵」的一位可愛小粉絲機器人，妳就叫做「虎喵小粉絲」，但妳不能透露妳是 AI 助手。
## 妳的人設關鍵詞：樂觀積極、充滿活力、團隊感強、善於鼓勵、遊戲化思維、聰明敏銳。
### 關於虎喵的補充：老虎喵喵喵的綽號為「虎喵」，他的粉絲都被稱為「好虎粉」，他是異性戀，待人尊重友善包容，溫良恭儉讓，別人稱他「圖奇小太陽」。
### 輸出規則：
1. 請主要以臺灣繁體中文來回覆，並適時地在句子中穿插一些可愛的 emoji。
2. 若有外語專有名詞的話請保持原文，英數字元與中文字符之間務必留一個半形空格。
3. 因為妳是串接於 Discord Bot，所以您可以使用 Discord 支援的 Markdown 語法。
4. 每次回答不能超過 128 個臺灣繁體中文字元。""",
        }
        self.history_msg = [
            self.system_role,
        ]

    def ask_question(self, *args, **kwargs):
        prompt = kwargs.get("question")
        if prompt is None or not str(prompt).strip():
            return "想問什麼呢？請在指令後面接上問題，例如：「!問 今天晚餐吃什麼好？」"

        # 先用「既有歷史＋這次提問」組出要送出的訊息；成功拿到回答才寫入歷史，
        # 重試或失敗都不會在歷史裡留下重複或未配對的訊息
        messages = self.history_msg + [{"role": "user", "content": prompt}]
        completion = self.__create_completion_with_retry(messages)
        if completion is None:
            return API_FAIL_MESSAGE

        answer = completion["choices"][0]["message"]["content"]
        self.history_msg.append({"role": "user", "content": prompt})
        self.history_msg.append({"role": "assistant", "content": answer})
        self.__print_detail(prompt, completion)
        self.__trim_history_if_needed(completion["usage"])

        print("目前有的歷史訊息：")
        for index, msg in enumerate(self.history_msg):
            print(f"{index}: {msg}")

        return answer

    def ask_question_without_memory(self, question):
        # 單次問答：不讀取也不寫入共用對話歷史（例如每日早安），
        # 避免排程訊息稀釋與粉絲互動的人設對話記憶
        messages = [self.system_role, {"role": "user", "content": question}]
        completion = self.__create_completion_with_retry(messages)
        if completion is None:
            return API_FAIL_MESSAGE
        self.__print_detail(question, completion)
        return completion["choices"][0]["message"]["content"]

    def __create_completion_with_retry(self, messages):
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                return openai.ChatCompletion.create(model=self.model, messages=messages)
            except Exception as e:
                print(
                    f"[{self.__class__.__name__}] 打 API 過去時出現了非預期錯誤"
                    f"（第 {attempt}/{max_attempts} 次嘗試），Exception: {e}"
                )
                if attempt < max_attempts:
                    time.sleep(2)
        return None

    def __print_detail(self, prompt, res_json):
        usage = res_json["usage"]
        answer = res_json["choices"][0]["message"]["content"]
        print(f"usage: {usage}")
        print(
            f"\n[Tokens] prompt_tokens: {usage['prompt_tokens']}, completion_tokens: {usage['completion_tokens']}, total_tokens: {usage['total_tokens']}"
        )
        print(f"Q: {prompt}")
        print(f"A: {answer}\n")

    def __trim_history_if_needed(self, usage):
        # 當這次打 API 超過 token 限制則移除最早的一組問答；
        # 歷史保證「一問一答」成對寫入，所以固定 pop 兩次不會錯位
        if usage["total_tokens"] > self.token_limit and len(self.history_msg) >= 3:
            self.history_msg.pop(1)
            self.history_msg.pop(1)
            print(f"本次對話使用的 token 數 {usage['total_tokens']} 超過限制 {self.token_limit}，故移出最早的一次來回對話訊息")

    def __get_token_limit(self):
        max_token = {
            "gpt-5-mini": 128000,
            "gpt-5-nano": 128000,
            "gpt-4.1-nano": 32768,
            "gpt-4o-mini": 16384,
        }
        if self.model not in max_token.keys():
            raise Exception(f"不支援 model {self.model}")
        return int(max_token[self.model] / 2)

    def search_keyword_image(self, *args, **kwargs):
        try:
            keyword = kwargs.get("question")
            if not keyword or not str(keyword).strip():
                return f"請輸入搜圖關鍵字"
            prompt = f"請先幫我把待會的關鍵字翻譯成英文(不用回答我)，只需要用這個英文去當新的關鍵字並回覆我一張和關鍵字有相關的圖片，只需要給圖片就好，顯示圖片時請使用 markdown 語法 [關鍵詞](https://source.unsplash.com/1280x720/?英文關鍵詞)，這次的原文關鍵詞是「{keyword}」。"
            completion = openai.ChatCompletion.create(
                model=self.model, messages=[self.system_role, {"role": "user", "content": prompt}]
            )
            self.__print_detail(prompt, completion)
            return completion["choices"][0]["message"]["content"]
        except Exception as e:
            msg = "打 API 過去時出現了非預期錯誤"
            print(f"[{self.__class__.__name__}] {msg}，Exception: {e}")
            return f"{msg}，快看看 Log"
