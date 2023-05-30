from config_utils import read_config_file
import openai

CONFIG = read_config_file()
openai.api_key = CONFIG.get("openai_api_key")


class OpenaiAPI:
    def __init__(self):
        self.model = "gpt-3.5-turbo"
        self.system_role = {
            "role": "system",
            "content": 'You are a lively and enthusiastic little fan of the handsome and humorous male game streamer "虎喵".',
        }

    def ask_question(self, prompt):
        try:
            prompt += f"\n請用繁體中文回答，感謝"
            completion = openai.ChatCompletion.create(
                model=self.model,
                messages=[self.system_role, {"role": "user", "content": prompt}],
                temperature=1,
                max_tokens=600,
            )
            self.print_detail(prompt, completion)
            return completion["choices"][0]["message"]["content"]
        except Exception as e:
            return f"打 API 過去時出現了非預期錯誤，Exception 為: {e}"

    def print_detail(self, prompt, res_json):
        usage = res_json["usage"]
        answer = res_json["choices"][0]["message"]["content"]
        print(
            f"[Tokens] 總共:{usage['total_tokens']} 提問:{usage['prompt_tokens']} 回答:{usage['completion_tokens']}"
        )
        print(f"Q: {prompt}")
        print(f"A: {answer}\n")

    def search_keywords_image(self, keywords):
        try:
            if len(keywords) == 0:
                return f"請輸入搜圖關鍵字"
            prompt = f"請先幫我把待會的關鍵字翻譯成英文(不用回答我)，只需要用這個英文去當新的關鍵字並回覆我一張和關鍵字有相關的圖片，只需要給圖片就好，顯示圖片時請使用 markdown 語法 [<關鍵詞>](https://source.unsplash.com/1280x720/?<關鍵詞>)，這次的關鍵詞是「{keywords}」。"
            completion = openai.ChatCompletion.create(
                model=self.model,
                messages=[self.system_role, {"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=600,
            )
            self.print_detail(prompt, completion)
            return completion["choices"][0]["message"]["content"]
        except Exception as e:
            msg = "打 API 過去時出現了非預期錯誤"
            print(f"[OpenAI_API] {msg}，Exception: {e}")
            return f"{msg}，快看看 Log"
