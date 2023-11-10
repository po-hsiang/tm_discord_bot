from config_utils import read_config_file
import openai

CONFIG = read_config_file()
openai.api_key = CONFIG.get("openai_api_key")


class OpenaiAPI:
    def __init__(self):
        self.model = CONFIG.get("openai_model")
        self.token_limit = self.__get_token_limit()
        self.system_role = {
            "role": "system",
            "content": f"妳是帥氣幽默的遊戲男實況主「虎喵」的一位可愛小粉絲機器人，"
            f"妳超級活潑而且相當熱情，且都用繁體中文回覆大家；然後虎喵的粉絲都被稱為「好虎粉」。",
        }
        self.history_msg = [
            self.system_role,
        ]

    def ask_question(self, *args, **kwargs):
        try:
            prompt = kwargs.get("question")
            self.history_msg.append({"role": "user", "content": prompt})
            completion = openai.ChatCompletion.create(
                model=self.model,
                messages=self.history_msg,
                temperature=1.1,
            )
            self.__print_detail(prompt, completion)
            answer = completion["choices"][0]["message"]["content"]
            self.history_msg.append({"role": "assistant", "content": answer})
            for index, msg in enumerate(self.history_msg):
                print(f"{index}: {msg}")
            return answer
        except Exception as e:
            msg = "打 API 過去時出現了非預期錯誤"
            print(f"[{self.__class__.__name__}] {msg}，Exception: {e}")
            return f"{msg}，快看看 Log"

    def __print_detail(self, prompt, res_json):
        usage = res_json["usage"]
        answer = res_json["choices"][0]["message"]["content"]
        print(
            f"\n[Tokens] 總共:{usage['total_tokens']} 提問:{usage['prompt_tokens']} 回答:{usage['completion_tokens']}"
        )
        print(f"Q: {prompt}")
        print(f"A: {answer}\n")

        if usage["total_tokens"] > self.token_limit:
            self.history_msg.pop(1)
            self.history_msg.pop(1)

    def __get_token_limit(self):
        max_token = {
            "gpt-4-1106-preview": 128000,
            "gpt-4-32k": 32768,
            "gpt-4": 8192,
            "gpt-3.5-turbo-1106": 16385,
            "gpt-3.5-turbo-16k": 16385,
            "gpt-3.5-turbo": 4096,
        }
        if self.model not in max_token.keys():
            raise Exception(f"不支援 model {self.model}")
        return int(max_token[self.model] / 2)

    def search_keyword_image(self, *args, **kwargs):
        try:
            keyword = kwargs.get("question")
            if len(keyword) == 0:
                return f"請輸入搜圖關鍵字"
            prompt = f"請先幫我把待會的關鍵字翻譯成英文(不用回答我)，只需要用這個英文去當新的關鍵字並回覆我一張和關鍵字有相關的圖片，只需要給圖片就好，顯示圖片時請使用 markdown 語法 [關鍵詞](https://source.unsplash.com/1280x720/?英文關鍵詞)，這次的原文關鍵詞是「{keyword}」。"
            completion = openai.ChatCompletion.create(
                model=self.model,
                messages=[self.system_role, {"role": "user", "content": prompt}],
                temperature=0,
            )
            self.__print_detail(prompt, completion)
            return completion["choices"][0]["message"]["content"]
        except Exception as e:
            msg = "打 API 過去時出現了非預期錯誤"
            print(f"[{self.__class__.__name__}] {msg}，Exception: {e}")
            return f"{msg}，快看看 Log"
