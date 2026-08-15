from pathlib import Path

import pygsheets
from config_utils import read_config_file

CONFIG = read_config_file()


class GoogleSheetUtils:
    @classmethod
    def init_spreadsheet_api(cls):
        service_file = (
            Path(__file__).resolve().parent.parent / "json" / CONFIG.get("google_credential_file")
        )
        gsheets_app = pygsheets.authorize(service_file=service_file)
        return gsheets_app
