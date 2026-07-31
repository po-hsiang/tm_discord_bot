# tm_discord_bot — 虎喵小粉絲 Discord Bot 🐯

一隻為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群打造的 Discord 互動機器人。
以「虎喵小粉絲」的人設與好虎粉互動，功能涵蓋 AI 聊天問答（含圖片/貼圖理解）、每日早安招呼、隨機點歌、吃什麼抽選、抽籤、二選一淘汰賽等。

> 版本：`0.1.9`｜語言：Python 3.8+｜套件管理：uv｜AI：n8n AI Agent 微服務｜部署：Docker Compose

**架構**：AI 相關能力（模型、人設、工具、對話記憶）獨立於 n8n「Discord AI Agent」工作流維護，
bot 本體只負責 Discord 連線、指令路由與原生功能，兩邊可各自演進。

---

## ✨ 功能一覽

機器人只回應設定檔中指定的頻道（`assistant_channel_id` / `test_channel_id`），全形「！」會自動轉為半形「!」。

| 指令 | 說明 | 資料來源 |
| --- | --- | --- |
| `!問 <問題>`、`!gpt <問題>` | 轉交 n8n AI Agent 以「虎喵小粉絲」人設回答；支援同訊息附圖或貼圖（Gemini 視覺分析）、可查即時資訊（搜尋等工具）、同頻道共享最近 10 輪對話記憶 | n8n AI Agent 微服務 |
| `!抽` | 抽 10 支籤（黑 / 黃 / 彩虹，權重 94.3 / 5.1 / 0.6，含保底機制：10 抽必有黃籤以上） | 內建 |
| `!吃`、`!吃啥`、`!<分類名>` | 從 Google 試算表隨機抽一個「今天吃什麼」，可指定分類 | Google Sheets |
| `!聽`、`!歌`、`!聽歌`、`!listen`、`!song` | 從虎喵的 YouTube 歌單隨機推薦一首歌 | YouTube Data API |
| `!查歌單 <關鍵字>` | 搜尋歌單中標題或頻道名稱含關鍵字的歌曲（自動分段避開 Discord 2000 字上限） | YouTube Data API |
| `!21` | 開始 16 強二選一淘汰賽，之後輸入 `左`/`A` 或 `右`/`B` 逐輪選出冠軍 | Google Sheets 候選清單 |
| `!心結` | 彩蛋固定回覆 | 內建 |

### ⏰ 排程功能

- **每日早安（07:30）**：由 n8n AI Agent 生成每天不重複的活力招呼語（使用獨立的 `morning-call` 記憶 session，能看見前幾天的招呼語以確保變化），並附上一首歌單隨機推薦，發送到閒聊頻道（`chitchat_channel_id`）。
- `RemindSystem` 亦支援自訂「指定時間 + 指定星期」的提醒訊息（目前程式內為註解狀態，未啟用）。

---

## 📁 專案結構

```
tm_discord_bot/
├── Dockerfile                  # Python 3.8-slim + uv 建置
├── compose.yaml                # Docker Compose（TZ=Asia/Taipei、restart: always）
├── pyproject.toml              # 相依定義（PEP 621，由 uv 管理）
├── uv.lock                     # uv 鎖定檔（入版控，確保可重現安裝）
├── .python-version             # 釘住 Python 3.8（uv 自動選用）
└── tm_discord_bot/
    ├── config/
    │   └── config.ini          # YouTube API URL、下載資料夾等設定（video analysis 用）
    ├── json/                   # ⚠️ 不入版控（.gitignore: *.json）
    │   ├── config.json         # 各服務金鑰與頻道 ID（見下方設定說明）
    │   └── <service_account>.json  # Google 服務帳戶憑證（pygsheets 用）
    ├── scripts/
    │   ├── main.py             # 進入點：Discord client、事件分派
    │   ├── config_utils.py     # 讀取 config.json
    │   ├── google_sheet_utils.py  # pygsheets 授權初始化
    │   └── plugins/
    │       ├── auto_reply_system.py     # 指令路由（字串回覆 / 函式回覆 / 遊戲）
    │       ├── ai_agent_client.py       # n8n AI Agent 微服務客戶端（!問 / 早安）
    │       ├── youtube_api.py           # 歌單載入、隨機點歌、關鍵字搜尋
    │       ├── eat_what_system.py       # Google Sheets 讀取吃什麼清單
    │       ├── pull_system.py           # 加權抽籤 + 保底
    │       ├── two_choices_one_system.py # 二選一淘汰賽狀態機
    │       ├── remind_system.py         # 早安 / 定時提醒（Singleton）
    │       ├── youtube_handler.py       # (開發中) 影片資訊 / CC 字幕擷取
    │       ├── analyzer.py              # (開發中，尚不可執行) 字幕摘要分析
    │       └── video analysis.py        # (開發中) 影片分析進入點
    └── utils/
        └── config_utils.py     # 讀取 config.json / config.ini（video analysis 用）
```

---

## 🚀 快速開始

### 1. 準備設定檔

在 `tm_discord_bot/json/` 建立 `config.json`：

```json
{
  "discord_bot_token": "你的 Discord Bot Token",
  "google_credential_file": "你的服務帳戶憑證檔名.json",
  "what_to_eat_url": "Google 試算表完整網址",
  "youtube_developer_key": "你的 YouTube Data API Key",
  "my_yt_music_playlist_id": "YouTube 歌單 ID",
  "assistant_channel_id": 123456789012345678,
  "chitchat_channel_id": 123456789012345678,
  "test_channel_id": 123456789012345678
}
```

| 欄位 | 說明 |
| --- | --- |
| `discord_bot_token` | Discord Developer Portal 取得，需開啟 **Message Content Intent** |
| `google_credential_file` | 放在 `tm_discord_bot/json/` 內的 GCP 服務帳戶憑證檔名，該帳戶需有試算表讀取權限 |
| `what_to_eat_url` | 「吃什麼」試算表網址，工作表名稱須為 `工作表1`，每一欄第一列為分類名、其下為選項 |
| `youtube_developer_key` / `my_yt_music_playlist_id` | YouTube Data API v3 金鑰與播放清單 ID |
| `assistant_channel_id` / `test_channel_id` | 機器人監聽指令的頻道 ID（數字） |
| `chitchat_channel_id` | 每日早安訊息發送頻道 ID（數字） |

> 舊版的 `openai_api_key` / `openai_model` 欄位已不再使用（AI 已改走 n8n 微服務），留在檔案裡無妨、也可刪除。

### 2. 建立 .env（機敏環境變數）

複製 `.env.example` 為 `.env` 並填入實際值：

```env
YOUTUBE_API_KEY=your_youtube_data_api_key        # （影片分析開發模組使用）
N8N_API_KEY=your_n8n_api_key                     # n8n 管理 API（開發輔助用，bot 執行不需要）
N8N_AGENT_WEBHOOK_URL=http://host.docker.internal:5678/webhook/discord-ai-agent
N8N_WEBHOOK_SECRET=your_webhook_shared_secret    # 與 n8n Webhook 節點 Header Auth 相同（X-Webhook-Secret）
```

> `.env` 已加入 `.gitignore` 與 `.dockerignore`，不會進入版控或 Docker 映像；
> Docker 部署由 `compose.yaml` 的 `env_file` 於**啟動時**注入容器。
> AI 功能需要宿主機的 n8n 服務在線且「Discord AI Agent」工作流為啟用狀態。

### 3-A. 本機執行（uv）

```bash
uv sync                # 依 uv.lock 建立 .venv 並安裝相依（會自動使用 Python 3.8）
cd tm_discord_bot/scripts
uv run python main.py
```

> 注意：模組以 `scripts/` 為根目錄匯入（如 `from plugins.xxx import ...`），
> 請直接執行 `main.py`，勿以其他工作目錄用 `-m` 方式啟動。

### 3-B. Docker 部署（建議）

```bash
docker compose up -d --build
```

- 時區已設定為 `Asia/Taipei`（早安排程依此時區觸發）。
- `restart: always`：容器異常會自動重啟。

---

## 🔧 技術棧

| 類別 | 使用技術 |
| --- | --- |
| Discord | `discord` (discord.py) 2.3+，事件驅動（`on_ready` / `on_message`） |
| AI 對話 | n8n「Discord AI Agent」工作流（Webhook 微服務）：Gemini 模型＋人設＋工具（搜尋/Wikipedia/計算機/QuickChart/YTMusic MCP）＋按頻道的對話記憶；bot 端僅為 HTTP 客戶端（`ai_agent_client.py`，Header Auth＋60 秒逾時＋降級訊息） |
| 試算表 | `pygsheets` + GCP 服務帳戶 |
| YouTube | `google-api-python-client`（經 pygsheets 相依引入）、`youtube-transcript-api` |
| 排程 | `asyncio` 常駐迴圈（每 60 秒檢查一次是否到達目標時間） |

---

## ⚠️ 安全注意事項

- `tm_discord_bot/json/*.json`（Bot Token、API 金鑰、GCP 憑證）已被 `.gitignore` 排除，**請勿**將其加入版控。
- Docker 映像建置時會將 `json/` 一併打包進映像（執行時需要），請勿將此映像推送到公開 registry。

## 📌 已知限制

- 歌單與「吃什麼」清單皆於**啟動時載入一次**，資料異動後需重啟機器人。
- 二選一淘汰賽為全頻道共用狀態，同一時間僅能進行一場。
- `youtube_handler.py` / `analyzer.py` / `video analysis.py` 為開發中的影片分析功能，尚未串接到機器人主流程。
