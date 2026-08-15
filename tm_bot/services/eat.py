import logging
import random

from tm_bot.clients.google_sheets import GoogleSheetUtils

logger = logging.getLogger(__name__)

LOAD_FAIL_MESSAGE = "「吃什麼」清單暫時載入失敗，請稍後再試 🙏"


class EatWhatSystem:
    def __init__(self, sheet_url, credential_path):
        self.sheet_url = sheet_url
        self.credential_path = credential_path
        # 延遲載入：啟動時不抓試算表，首次使用（或 on_ready 預載）時才載入，
        # Google Sheets 故障時機器人仍可啟動，僅此功能暫時降級
        self.total_answers_list = []
        self.meal_commend_list = ["吃啥", "吃"]
        self.meal_dict = {}
        self._loaded = False

    def ensure_loaded(self):
        if self._loaded:
            return True
        try:
            gsheets_app = GoogleSheetUtils.authorize(self.credential_path)
            spread_sheet = gsheets_app.open_by_url(self.sheet_url)
            ws = spread_sheet.worksheet_by_title("工作表1")
            raw_data = ws.get_all_values(
                majdim="COLUMNS",
                include_tailing_empty_rows=False,
                include_tailing_empty=False,
            )
            # 先組進區域變數，全部成功才寫回，避免中途失敗留下不完整資料
            total_answers_list = []
            meal_commend_list = ["吃啥", "吃"]
            meal_dict = {}
            for columns in raw_data:
                meal_type = ""
                for index, value in enumerate(columns):
                    if value:
                        if index == 0:
                            meal_type = value
                            meal_dict[meal_type] = []
                            meal_commend_list.append(meal_type)
                        else:
                            total_answers_list.append(value)
                            meal_dict[meal_type].append(value)
            self.total_answers_list = total_answers_list
            self.meal_commend_list = meal_commend_list
            self.meal_dict = meal_dict
            self._loaded = True
        except Exception as e:
            logger.warning("載入「吃什麼」試算表失敗，之後使用時會再重試：%s", e)
        return self._loaded

    def get_meal_commend_list(self):
        self.ensure_loaded()
        return self.meal_commend_list

    def get_total_answers_list(self):
        self.ensure_loaded()
        return self.total_answers_list

    def choose_one_meal(self, msg):
        if not self.ensure_loaded() or not self.total_answers_list:
            return LOAD_FAIL_MESSAGE
        if msg in self.meal_dict:
            return random.choice(self.meal_dict[msg])
        else:
            return random.choice(self.total_answers_list)
