from configparser import ConfigParser
from dotenv import load_dotenv
from pathlib import Path
import json

# 載入專案根目錄的 .env，將機敏資訊（API 金鑰等）與程式碼隔離
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def read_config_file():
    config_path = Path(__file__).resolve().parent.parent / "json" / "config.json"  # 設定檔 config.json 的路徑
    try:
        with open(config_path, 'r', encoding="utf-8") as file:
            config_data = json.load(file)
            return config_data
    except FileNotFoundError:
        print(f"找不到 {config_path} 文件。")
        return None
    except json.JSONDecodeError as e:
        print(f"解析 {config_path} 文件時發生錯誤：{str(e)}")
        return None


def load_config():
    config_path = Path(__file__).resolve().parent.parent / "config" / f"config.ini"
    config = ConfigParser()
    config.read(config_path, encoding="utf-8")
    return config


config = load_config()
