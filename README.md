# tm_discord_bot — 虎喵小粉絲 Discord Bot 🐯

一隻為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群打造的 Discord 互動機器人。
以「虎喵小粉絲」的人設與好虎粉互動，功能涵蓋 AI 聊天問答（含圖片/貼圖理解）、YouTube 影片快速摘要、每日早安招呼、每晚台灣熱門話題、每週五遊戲特惠情報、隨機點歌、吃什麼抽選、抽籤等。

> 版本：`0.2.13`｜語言：Python 3.14｜套件管理：uv｜AI：n8n AI Agent 微服務｜部署：Docker Compose

**架構**：bot 本體只負責 Discord 連線、指令路由與輕量原生功能，重活外包給微服務——
AI 能力（模型、人設、工具、對話記憶）在 n8n「TM AI Agent」工作流（多客戶端共用）；
歌單能力（載入、快取 TTL 6 小時、多歌單搜尋、隨機選歌）在 `yt-music-mcp`（MCP＋REST 雙介面）；
影片快速摘要在 n8n「YouTube 影片快速摘要」工作流（串接 yt-music-mcp 的影片資訊/字幕端點＋Gemini 摘要）。
各服務獨立演進，LLM 金鑰只存在於 n8n、YouTube API Key 只存在於 yt-music-mcp，bot 端零金鑰。

---

## ✨ 功能一覽

機器人只回應設定檔中指定的頻道（`assistant_channel_id` / `test_channel_id` / `video_summary_channel_id`），全形「！」會自動轉為半形「!」。

頻道內採**混合模式**：

1. `!` 開頭 → 優先觸發特定指令（見下表）。
2. **其餘任何訊息——文字、圖片、貼圖——一律視為自然語言，直接與 AI 對話**（不需任何指令）；
   機器人以「回覆」形式回應、輸入期間顯示 typing，並忽略其他機器人（防互聊迴圈）。
   對話記憶以頻道為單位（最近 10 輪）。

### ⌨️ 指令列表

| 指令 | 說明 | 資料來源 |
| --- | --- | --- |
| （自然語言，免指令） | 以「虎喵小粉絲」人設對話；支援附圖或貼圖（Gemini 視覺分析）、可查即時資訊（搜尋等工具） | n8n AI Agent 微服務 |
| `!抽` | 抽 10 支籤（黑 / 黃 / 彩虹，權重 94.3 / 5.1 / 0.6，含保底機制：10 抽必有黃籤以上） | 內建 |
| `!吃`、`!吃啥`、`!<分類名>` | 從 Google 試算表隨機抽一個「今天吃什麼」，可指定分類 | Google Sheets |
| `!聽`、`!歌`、`!聽歌`、`!listen`、`!song` | 從虎喵的 YouTube 歌單隨機推薦一首歌 | yt-music-mcp 微服務 |
| `!查歌單 <關鍵字>` | 跨**全部歌單**搜尋標題或頻道名稱含關鍵字的歌曲（標示所屬歌單、自動分段避開 Discord 2000 字上限） | yt-music-mcp 微服務 |
| `!心結` | 彩蛋固定回覆 | 內建 |

> 舊的 `!問`／`!gpt` 已退役——直接說話即可；打了也會收到轉換提示。

### 📺 YouTube 影片快速摘要（專屬頻道，免指令）

在專屬頻道（`video_summary_channel_id`）**貼上 YouTube 影片連結即觸發**（測試頻道也會觸發）：

1. 機器人以 ⏳ reaction 表示處理中（約 10～30 秒）。
2. 完成後回覆 Embed 卡片：影片標題（可點擊）＋縮圖＋**重點大綱（2～4 點、每點一句話）**＋影片標籤（`#tag` 單行）＋頁尾「頻道名｜片長」。
3. 支援 `watch?v=`、`youtu.be/`、`/live/` 三種連結格式（`/shorts/` 不支援）；專屬頻道內非影片連結的訊息一律靜默忽略。
4. 同一支影片 6 小時內重複貼上直接回快取（不重打 LLM）；多人同時貼同一支影片只會發出一次請求。
5. 直播中、音樂類（MV/演奏/Topic 頻道）的影片會以文字婉拒；**超過 70 分鐘的影片不處理、也不回應**（靜默）。

> 流程：bot → n8n「YouTube 影片快速摘要」工作流 → yt-music-mcp（影片資訊＋CC 字幕）→ LLM 結構化輸出。
> 字幕來源三層遞補：**CC 字幕**（人工優先、自動生成次之）→ 無 CC 時改抓**低碼率音訊**（yt-music-mcp `/audio`，yt-dlp）交給 Gemini 轉錄＋摘要 → 音訊層技術性失敗時最後由 **Gemini 直接看影片**（YouTube URL）。
> 回應附 `source` 欄位（transcript/audio/video）標示摘要來源。

### ⏰ 排程功能

- **每日早安（07:30）**：由 n8n AI Agent 生成每天不重複的活力招呼語（使用獨立的 `morning-call` 記憶 session，能看見前幾天的招呼語以確保變化），**並以 `tw_weather` 工具播報今日全台天氣重點與貼心提醒**（天氣暫時取不到時自動略過），最後附上一首歌單隨機推薦，發送到閒聊頻道（`chitchat_channel_id`）。
- **每晚話題（19:30，與早安恰隔 12 小時）**：由 n8n AI Agent 呼叫 `tw_trends_news` 工具取得台灣 Google 熱搜與頭條，**濾除政治與悲劇社會案件**（優先挑娛樂/遊戲/動漫/科技/生活/體育類），以鄉民/活網仔口吻「劃重點」——一句話總結氛圍＋emoji 條列 2～4 個話題（無開場白與結尾），發送到閒聊頻道；使用獨立的 `night-trends` 記憶 session 讓連續幾晚的內容有變化；若過濾後無合適話題則自起輕鬆話題替代，來源故障時**間隔 60 秒重試一次**，仍失敗才當晚**靜默跳過**（不貼降級訊息）。
- **週末遊戲情報（每週五 22:00）**：由 n8n AI Agent 呼叫 `game_deals` 工具取得 **Epic 本週免費遊戲**（附領取截止日）與 **Steam 特惠精選**（折扣 50% 以上或知名大作，3～5 款、台幣定價），以鄉民口吻整理發送到遊戲頻道（`game_deals_channel_id`），遊戲名附 **Markdown 商店連結**（`[名稱](<網址>)` 角括號格式抑制預覽卡片；工具未提供連結時自動只寫名稱）；使用獨立的 `game-deals` 記憶 session；來源故障時間隔 60 秒重試一次，仍失敗（或工具回報無資料）當週**靜默跳過**。
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
            ├── ai_agent_client.py       # n8n AI Agent 微服務客戶端（自然語言對話 / 排程訊息）
            ├── video_summary.py         # n8n 影片快速摘要客戶端（URL 解析 / TTL 快取 / Embed）
            ├── song_picker.py           # yt-music-mcp 歌單微服務客戶端（點歌 / 查歌單）
            ├── eat_what_system.py       # Google Sheets 讀取吃什麼清單
            ├── pull_system.py           # 加權抽籤 + 保底
            └── remind_system.py         # 早安 / 晚間話題 / 定時提醒（Singleton）
```

---

## 🚀 快速開始

### 1. 建立 .env（機敏資訊集中於此）

複製 `.env.example` 為 `.env` 並填入實際值：

| 環境變數 | 說明 |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord Developer Portal 取得，需開啟 **Message Content Intent** |
| `GOOGLE_CREDENTIAL_FILE` | 放在 `tm_discord_bot/json/` 內的 GCP 服務帳戶憑證**檔名**，該帳戶需有試算表讀取權限 |
| `WHAT_TO_EAT_URL` | 「吃什麼」試算表網址，工作表名稱須為 `工作表1`，每一欄第一列為分類名、其下為選項 |
| `YT_MUSIC_API_URL` | yt-music-mcp 歌單微服務（bot 與其同在 `ai-net` docker 網路，以服務名直連；本機直跑改 `http://127.0.0.1:8765`） |
| `N8N_AGENT_WEBHOOK_URL` | n8n「TM AI Agent」webhook（容器經 `host.docker.internal` 直連宿主機） |
| `N8N_YT_SUMMARY_WEBHOOK_URL` | n8n「YouTube 影片快速摘要」webhook（與 AI Agent 共用 `N8N_WEBHOOK_SECRET`） |
| `N8N_WEBHOOK_SECRET` | webhook Header Auth 共享密鑰（header 名稱 `X-Webhook-Secret`） |
| `N8N_API_KEY` | n8n 管理 API 金鑰（開發輔助用，bot 執行期不需要） |

> `.env` 已加入 `.gitignore` 與 `.dockerignore`，不進版控也不進映像；
> Docker 部署由 `compose.yaml` 的 `env_file` 於**啟動時**注入容器。
> AI 功能需要宿主機的 n8n 服務在線且「TM AI Agent」工作流為啟用狀態。

### 2. 設定 config.ini（非機敏設定，入版控）

編輯 `tm_discord_bot/config/config.ini`：

```ini
[discord]
assistant_channel_id = 助手頻道 ID（指令＋自然語言 AI 對話）
test_channel_id = 測試頻道 ID（同上，貼影片連結也會觸發摘要）
chitchat_channel_id = 早安與晚間話題頻道 ID
video_summary_channel_id = 影片快速摘要專屬頻道 ID（留空則僅測試頻道生效）
game_deals_channel_id = 週五遊戲特惠情報頻道 ID
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
| AI 對話 | n8n「TM AI Agent」工作流（Webhook 微服務，多客戶端共用）：Gemini 模型＋人設＋工具（搜尋/Wikipedia/計算機/QuickChart/YTMusic MCP/台灣熱搜新聞/台灣天氣/遊戲特惠）＋按頻道的對話記憶；bot 端僅為 HTTP 客戶端（`ai_agent_client.py`，Header Auth＋逾時預設 60 秒、呼叫端可覆寫（晚間話題 120 秒）＋降級訊息） |
| 影片摘要 | n8n「YouTube 影片快速摘要」工作流：yt-music-mcp `/video`（時長/直播預檢）＋`/transcript`（CC 字幕）→ LLM 結構化輸出（重點大綱 2～4 點＋影片標籤）；無 CC 時二層備援：`/audio` 低碼率音訊→Gemini 轉錄摘要 → Gemini 直接看影片；bot 端僅為 HTTP 客戶端（`video_summary.py`，200 秒逾時＋TTL 6 小時快取＋同影片並發去重） |
| 試算表 | `pygsheets` + GCP 服務帳戶 |
| 歌單 | `yt-music-mcp` 微服務（MCP＋REST 雙介面）：載入、快取（TTL 6 小時）、跨歌單搜尋、隨機選歌全在伺服器端；bot 端僅為 HTTP 客戶端（`song_picker.py`），不需 YouTube API Key |
| 排程 | `asyncio` 常駐迴圈（每 60 秒檢查一次是否到達目標時間） |

---

## ⚠️ 安全注意事項

- 機敏資訊集中於 `.env`（gitignore／dockerignore 皆排除）；GCP 憑證放 `tm_discord_bot/json/`（gitignore 排除、Docker 以唯讀 volume 掛載）。
- **Docker 映像本身不含任何機敏檔案**：金鑰由 `env_file` 於啟動時注入、憑證由 volume 提供。

## 📌 已知限制

- 「吃什麼」清單於**首次使用時載入並快取**，資料異動後需重啟機器人（歌單則由微服務端 TTL 6 小時自動更新，不需重啟）。
- 影片摘要：直播中、`/shorts/`、音樂類（MV/演奏/Topic 頻道）不支援；超過 70 分鐘的影片靜默忽略（不回應）；無 CC 字幕的影片改走音訊轉錄備援（費用略高、耗時約 1 分鐘）。
