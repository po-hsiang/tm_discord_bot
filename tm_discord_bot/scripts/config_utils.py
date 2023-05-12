from pathlib import Path
import json


def read_config_file():
    config_path = Path("..") / "json" / "config.json"  # 設定檔 config.json 的路徑
    try:
        with open(config_path, 'r') as file:
            config_data = json.load(file)
            return config_data
    except FileNotFoundError:
        print(f"找不到 {config_path} 文件。")
        return None
    except json.JSONDecodeError as e:
        print(f"解析 {config_path} 文件時發生錯誤：{str(e)}")
        return None
