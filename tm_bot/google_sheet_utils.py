import pygsheets

from tm_bot.config_utils import PROJECT_ROOT, read_config_file

CONFIG = read_config_file()


class GoogleSheetUtils:
    @classmethod
    def init_spreadsheet_api(cls):
        # GCP 服務帳戶憑證放在專案根的 secrets/（不入版控，Docker 以唯讀 volume 掛載）
        service_file = PROJECT_ROOT / "secrets" / CONFIG.get("google_credential_file")
        gsheets_app = pygsheets.authorize(service_file=service_file)
        return gsheets_app
