# tm_discord_bot — 虎喵小粉絲 Discord Bot 🐯

一隻為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群打造的 Discord 互動機器人。
以「虎喵小粉絲」的人設與好虎粉互動，功能涵蓋 AI 聊天問答（含圖片/貼圖理解）、每日早安招呼、隨機點歌、吃什麼抽選、抽籤、二選一淘汰賽等。

> 版本：`0.1.9`｜語言：Python 3.14｜套件管理：uv｜AI：n8n AI Agent 微服務｜部署：Docker Compose

**架構**：AI 相關能力（模型、人設、工具、對話記憶）獨立於 n8n「Discord AI Agent」工作流維護，
bot 本體只負責 Discord 連線、指令路由與原生功能，兩邊可各自演進。

---

## ✨ 功能一覽

機器人只回應設定檔中指定的頻道（`assistant_channel_id` / `test_channel_id`），全形「！」會自動轉為半形「!」。

### 💬 AI 自由對話頻道（免指令）

在 `config.ini` 的 `ai_chat_channel_id`（正式）／`ai_chat_test_channel_id`（測試）指定頻道後，
該頻道內**任何訊息——文字、圖片、貼圖——都直接交給 AI**，不需要打 `!問`；
機器人以「回覆」形式回應、輸入期間顯示 typing 指示，並忽略其他機器人的發言（防互聊迴圈）。
對話記憶以頻道為單位（最近 10 輪）。留空則此功能停用。

### ⌨️ 指令列表

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
├── Dockerfile                  # Python 3.14-slim + uv 建置
├── compose.yaml                # Docker Compose（TZ=Asia/Taipei、restart: always）
├── pyproject.toml              # 相依定義（PEP 621，由 uv 管理）
├── uv.lock                     # uv 鎖定檔（入版控，確保可重現安裝）
├── .python-version             # 釘住 Python 3.14（uv 自動下載選用）
└── tm_discord_bot/
    ├── config/
    │   └── config.ini          # 非機敏設定：各頻道 ID、歌單 ID（入版控）
    ├── json/                   # ⚠️ 不入版控（.gitignore: *.json）、不進映像（volume 掛載）
    │   └── <service_account>.json  # Google 服務帳戶憑證（pygsheets 用）
    └── scripts/
        ├── main.py             # 進入點：Discord client、事件分派、AI 頻道路由
        ├── config_utils.py     # 統一設定讀取：.env（機敏）＋ config.ini（非機敏）
        ├── google_sheet_utils.py  # pygsheets 授權初始化
        └── plugins/
            ├── auto_reply_system.py     # 指令路由（字串回覆 / 函式回覆 / 遊戲）
            ├── ai_agent_client.py       # n8n AI Agent 微服務客戶端（AI 頻道 / !問 / 早安）
            ├── youtube_api.py           # 歌單載入、隨機點歌、關鍵字搜尋
            ├── eat_what_system.py       # Google Sheets 讀取吃什麼清單
            ├── pull_system.py           # 加權抽籤 + 保底
            ├── two_choices_one_system.py # 二選一淘汰賽狀態機
            └── remind_system.py         # 早安 / 定時提醒（Singleton）
```

---

## 🚀 快速開始

### 1. 建立 .env（機敏資訊集中於此）

複製 `.env.example` 為 `.env` 並填入實際值：

| 環境變數 | 說明 |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord Developer Portal 取得，需開啟 **Message Content Intent** |
| `YOUTUBE_API_KEY` | YouTube Data API v3 金鑰（點歌 / 查歌單） |
| `GOOGLE_CREDENTIAL_FILE` | 放在 `tm_discord_bot/json/` 內的 GCP 服務帳戶憑證**檔名**，該帳戶需有試算表讀取權限 |
| `WHAT_TO_EAT_URL` | 「吃什麼」試算表網址，工作表名稱須為 `工作表1`，每一欄第一列為分類名、其下為選項 |
| `N8N_AGENT_WEBHOOK_URL` | n8n「Discord AI Agent」webhook（容器經 `host.docker.internal` 直連宿主機） |
| `N8N_WEBHOOK_SECRET` | webhook Header Auth 共享密鑰（header 名稱 `X-Webhook-Secret`） |
| `N8N_API_KEY` | n8n 管理 API 金鑰（開發輔助用，bot 執行期不需要） |

> `.env` 已加入 `.gitignore` 與 `.dockerignore`，不進版控也不進映像；
> Docker 部署由 `compose.yaml` 的 `env_file` 於**啟動時**注入容器。
> AI 功能需要宿主機的 n8n 服務在線且「Discord AI Agent」工作流為啟用狀態。

### 2. 設定 config.ini（非機敏設定，入版控）

編輯 `tm_discord_bot/config/config.ini`：

```ini
[discord]
assistant_channel_id = 指令頻道 ID
test_channel_id = 測試指令頻道 ID
chitchat_channel_id = 早安訊息頻道 ID
ai_chat_channel_id = 正式 AI 自由對話頻道 ID（留空＝停用）
ai_chat_test_channel_id = 測試 AI 自由對話頻道 ID（留空＝停用）

[youtube]
my_yt_music_playlist_id = YouTube 歌單 ID
```

> 修改 `config.ini` 後需重新部署（`docker compose up -d --build`）才會生效。

### 3-A. 本機執行（uv）

```bash
uv sync                # 依 uv.lock 建立 .venv 並安裝相依（會自動下載並使用 Python 3.14）
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

- 機敏資訊集中於 `.env`（gitignore／dockerignore 皆排除）；GCP 憑證放 `tm_discord_bot/json/`（gitignore 排除、Docker 以唯讀 volume 掛載）。
- **Docker 映像本身不含任何機敏檔案**：金鑰由 `env_file` 於啟動時注入、憑證由 volume 提供。

## 📌 已知限制

- 歌單與「吃什麼」清單於**首次使用時載入並快取**，資料異動後需重啟機器人。
- 二選一淘汰賽為全頻道共用狀態，同一時間僅能進行一場。
