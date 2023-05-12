from config_utils import read_config_file
from pathlib import Path
import pygsheets

CONFIG = read_config_file()


class GoogleSheetUtils:
    @classmethod
    def init_spreadsheet_api(cls):
        service_file = Path(f"..") / "json" / CONFIG.get('google_credential_file')
        gsheets_app = pygsheets.authorize(service_file=service_file)
        return gsheets_app
