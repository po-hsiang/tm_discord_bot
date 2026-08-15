import pygsheets


class GoogleSheetUtils:
    @staticmethod
    def authorize(credential_path):
        """以 GCP 服務帳戶憑證建立 pygsheets 連線（憑證路徑由呼叫端提供）。"""
        return pygsheets.authorize(service_file=credential_path)
