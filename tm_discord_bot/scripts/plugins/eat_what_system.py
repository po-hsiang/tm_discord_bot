from google_sheet_utils import GoogleSheetUtils
from config_utils import read_config_file
import random

CONFIG = read_config_file()


class EatWhatSystem:
    def __init__(self):
        gsheets_app = GoogleSheetUtils.init_spreadsheet_api()
        spread_sheet = gsheets_app.open_by_url(CONFIG.get("what_to_eat_url"))
        ws = spread_sheet.worksheet_by_title("工作表1")
        raw_data = ws.get_all_values(
            majdim="COLUMNS",
            include_tailing_empty_rows=False,
            include_tailing_empty=False,
        )
        self.total_answers_list = list()
        self.meal_commend_list = ["吃啥", "吃"]
        self.meal_dict = dict()
        for columns in raw_data:
            meal_type = ""
            for index, value in enumerate(columns):
                if value:
                    if index == 0:
                        meal_type = value
                        self.meal_dict[meal_type] = list()
                        self.meal_commend_list.append(meal_type)
                    else:
                        self.total_answers_list.append(value)
                        self.meal_dict[meal_type].append(value)

    def get_meal_commend_list(self):
        return self.meal_commend_list

    def choose_one_meal(self, msg):
        if msg in self.meal_dict:
            return random.choice(self.meal_dict[msg])
        else:
            return random.choice(self.total_answers_list)
