from pathlib import Path
import json


def read_config_file():
    # 設定檔 config.json 的路徑（resolve() 轉絕對路徑，避免相對匯入時解析到錯誤位置）
    config_path = Path(__file__).resolve().parent.parent / "json" / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise RuntimeError(f"找不到設定檔 {config_path}，請依 README「快速開始」章節建立 config.json")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"解析設定檔 {config_path} 失敗（JSON 格式錯誤）：{e}")
