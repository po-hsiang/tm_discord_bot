# tm_discord_bot — 虎喵小粉絲 Discord Bot 🐯

一隻為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群打造的 Discord 互動機器人。
以「虎喵小粉絲」的人設與好虎粉互動，功能涵蓋 AI 聊天問答（含圖片/貼圖理解）、YouTube 影片快速摘要、每日早安招呼、每晚台灣熱門話題、每週五遊戲特惠情報、隨機點歌、吃什麼抽選、抽籤等。

> 版本：`0.3.0`｜語言：Python 3.14｜套件管理：uv｜AI：n8n AI Agent 微服務｜部署：Docker Compose

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

- **每日早安（07:30）**：由 n8n AI Agent 生成每天不重複的活力招呼語（使用獨立的 `morning-call` 記憶 session，能看見前幾天的招呼語以確保變化），**並以 `tw_weather` 工具播報今日全台天氣重點與貼心提醒**（天氣暫時取不到時自動略過），最後附上一首歌單隨機推薦，發送到閒聊頻道（`chitchat_channel_id`）。**遇到節日或補假自動加彩蛋**——臺灣國定假日（含補假）、人氣節日（西洋情人節/萬聖節/平安夜/跨年夜/母親節/父親節等）、農曆節日（七夕/元宵/中元/重陽，閏月不算）與節氣（立冬/冬至）以 `holidays`＋`cnlunar` 套件**全離線**判斷：節日→應景祝福融入招呼語；連假補假日→體恤出遊、聊聊塞車去哪玩；查詢失敗照常打招呼。
- **每晚話題（19:30，與早安恰隔 12 小時）**：由 n8n AI Agent 呼叫 `tw_trends_news` 工具取得台灣 Google 熱搜與頭條，**濾除政治與悲劇社會案件**（優先挑娛樂/遊戲/動漫/科技/生活/體育類），以鄉民/活網仔口吻「劃重點」——一句話總結氛圍＋emoji 條列 2～4 個話題（無開場白與結尾），發送到閒聊頻道；使用獨立的 `night-trends` 記憶 session 讓連續幾晚的內容有變化；若過濾後無合適話題則自起輕鬆話題替代，來源故障時**間隔 60 秒重試一次**，仍失敗才當晚**靜默跳過**（不貼降級訊息）。
- **週末遊戲情報（每週五 22:00）**：由 n8n AI Agent 呼叫 `game_deals` 工具取得 **Epic 本週免費遊戲**（附領取截止日）與 **Steam 特惠精選**（折扣 50% 以上或知名大作，3～5 款、台幣定價），以鄉民口吻整理發送到遊戲頻道（`game_deals_channel_id`），遊戲名附 **Markdown 商店連結**（`[名稱](<網址>)` 角括號格式抑制預覽卡片；工具未提供連結時自動只寫名稱）；使用獨立的 `game-deals` 記憶 session；來源故障時間隔 60 秒重試一次，仍失敗（或工具回報無資料）當週**靜默跳過**。

> 排程表定義在 `tm_bot/services/scheduler/jobs.py` 的 `build_jobs()`：一則推播就是一個
> `ScheduledJob(標籤, 時間, 頻道, 內容產生函式, weekdays=…)`，要新增或調整推播只需動這張表。
> 啟動時會在 log 印出實際生效的排程（`排程已啟動：早安 7:30、晚間話題 19:30、遊戲情報 22:00`）。

---

## 🏗️ 架構分層

程式碼依職責分成四層，**依賴方向單向**：

```
cogs（指令與事件）→ services（領域邏輯）→ clients（外部系統）
                  ↘ ui（Discord 呈現）
```

| 層 | 職責 | 規則 |
| --- | --- | --- |
| `cogs/` | 收 Discord 訊息、呼叫服務、回覆 | 薄；不放商業邏輯 |
| `services/` | 領域邏輯（抽籤、節日、排程、連結解析） | **完全不 import discord**，可純函式測試 |
| `clients/` | 對外呼叫（n8n、yt-music-mcp、Google Sheets） | 只負責 I/O 與錯誤轉譯，不做業務判斷 |
| `ui/` | Embed、訊息分段等呈現細節 | 不做 I/O |
| `bot.py` | 唯一的組裝點與訊息路由 | 知道所有零件怎麼拼；其他模組彼此不必知道 |

**要加一個新指令**：在 `tm_bot/cogs/` 新增一個檔案（一個 `commands.Cog` 子類別 ＋ 檔尾的
`async def setup(bot)`），再把模組路徑加進 `bot.py` 的 `EXTENSIONS`——不需要修改任何既有檔案。

---

## 📁 專案結構

```
tm_discord_bot/
├── Dockerfile                  # Python 3.14-slim + uv 建置
├── compose.yaml                # Docker Compose（TZ=Asia/Taipei、restart: always）
├── pyproject.toml              # 相依定義（PEP 621）＋ ruff 設定
├── uv.lock                     # uv 鎖定檔（入版控，確保可重現安裝）
├── .python-version             # 釘住 Python 3.14（uv 自動下載選用）
├── config/
│   └── config.ini              # 非機敏設定：各頻道 ID（入版控）
├── secrets/                    # ⚠️ 不入版控、不進映像（以唯讀 volume 掛載）
│   └── <service_account>.json  # Google 服務帳戶憑證（pygsheets 用）
├── tests/                      # 單元測試（目錄結構鏡射 tm_bot/）
└── tm_bot/
    ├── __main__.py             # 進入點：python -m tm_bot
    ├── bot.py                  # 組裝點：建客戶端、掛 Cog、啟動排程、訊息路由
    ├── config.py               # 設定：.env（機敏）＋ config.ini（非機敏）→ Settings 物件
    ├── cogs/                   # 指令與事件（一個功能一個檔，可熱重載）
    │   ├── misc.py             #   !心結、已退役指令提示
    │   ├── draw.py             #   !抽
    │   ├── song.py             #   !聽、!查歌單
    │   ├── eat.py              #   !吃、!吃啥、!<分類名>（動態指令）
    │   ├── ai_chat.py          #   自然語言 → AI
    │   └── video_summary.py    #   影片連結 → 摘要（含同影片並發去重）
    ├── services/               # 領域邏輯（不 import discord）
    │   ├── draw.py             #   加權抽籤 + 保底
    │   ├── eat.py              #   Google Sheets 吃什麼清單
    │   ├── holiday.py          #   節日/補假/農曆節日/節氣（holidays＋cnlunar 離線計算）
    │   ├── youtube.py          #   YouTube 連結解析
    │   └── scheduler/
    │       ├── runner.py       #     排程引擎：什麼時候跑
    │       ├── jobs.py         #     排程表與內容產生：跑什麼
    │       └── prompts.py      #     三段排程 Prompt 文案（調文案只動這裡）
    ├── clients/                # 外部系統呼叫
    │   ├── http.py             #   n8n webhook 共用 POST（Header Auth、逾時、錯誤轉譯）
    │   ├── ai_agent.py         #   n8n AI Agent
    │   ├── yt_summary.py       #   n8n 影片摘要（TTL 6 小時快取）
    │   ├── yt_music.py         #   yt-music-mcp 歌單微服務
    │   └── google_sheets.py    #   pygsheets 授權
    └── ui/                     # Discord 呈現
        ├── embeds.py           #   摘要 Embed 與錯誤文案
        └── chunking.py         #   2000 字上限分段送出
```

---

## 🚀 快速開始

### 1. 建立 .env（機敏資訊集中於此）

複製 `.env.example` 為 `.env` 並填入實際值：

| 環境變數 | 說明 |
| --- | --- |
| `DISCORD_BOT_TOKEN` | Discord Developer Portal 取得，需開啟 **Message Content Intent** |
| `GOOGLE_CREDENTIAL_FILE` | 放在專案根 `secrets/` 內的 GCP 服務帳戶憑證**檔名**，該帳戶需有試算表讀取權限 |
| `WHAT_TO_EAT_URL` | 「吃什麼」試算表網址，工作表名稱須為 `工作表1`，每一欄第一列為分類名、其下為選項 |
| `YT_MUSIC_API_URL` | yt-music-mcp 歌單微服務（bot 與其同在 `ai-net` docker 網路，以服務名直連；本機直跑改 `http://127.0.0.1:8765`） |
| `N8N_AGENT_WEBHOOK_URL` | n8n「TM AI Agent」webhook（容器經 `host.docker.internal` 直連宿主機） |
| `N8N_YT_SUMMARY_WEBHOOK_URL` | n8n「YouTube 影片快速摘要」webhook（與 AI Agent 共用 `N8N_WEBHOOK_SECRET`） |
| `N8N_WEBHOOK_SECRET` | webhook Header Auth 共享密鑰（header 名稱 `X-Webhook-Secret`） |
| `N8N_API_KEY` | n8n 管理 API 金鑰（開發輔助用，bot 執行期不需要） |

> `.env` 與 `secrets/` 已加入 `.gitignore` 與 `.dockerignore`，不進版控也不進映像；
> Docker 部署由 `compose.yaml` 的 `env_file` 於**啟動時**注入容器。
> AI 功能需要宿主機的 n8n 服務在線且「TM AI Agent」工作流為啟用狀態。

### 2. 設定 config.ini（非機敏設定，入版控）

編輯 `config/config.ini`：

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
uv sync                     # 依 uv.lock 建立 .venv 並安裝相依（會自動下載並使用 Python 3.14）
uv run python -m tm_bot     # 於專案根目錄執行
```

開發輔助指令（皆於專案根執行）：

```bash
uv run ruff check . --fix   # lint（規則定義於 pyproject.toml，與 CI 相同）
uv run ruff format .        # 格式化
uv run python -m unittest discover -s tests   # 單元測試（不需 .env 與外部服務）
```

> 注意：`tm_bot` 為套件，請以 `python -m tm_bot` 於**專案根目錄**啟動；
> 用 `python tm_bot/__main__.py` 會讓絕對匯入失效。

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
| Discord | `discord` (discord.py) 2.3+，`commands.Bot` ＋ Cogs；`setup_hook` 掛載擴充與啟動排程、`on_message` 統一路由 |
| AI 對話 | n8n「TM AI Agent」工作流（Webhook 微服務，多客戶端共用）：Gemini 模型＋人設＋工具（搜尋/Wikipedia/計算機/QuickChart/YTMusic MCP/台灣熱搜新聞/台灣天氣/遊戲特惠）＋按頻道的對話記憶；bot 端僅為 HTTP 客戶端（`clients/ai_agent.py`，Header Auth＋逾時預設 60 秒、呼叫端可覆寫（晚間話題 120 秒）＋降級訊息） |
| 影片摘要 | n8n「YouTube 影片快速摘要」工作流：yt-music-mcp `/video`（時長/直播預檢）＋`/transcript`（CC 字幕）→ LLM 結構化輸出（重點大綱 2～4 點＋影片標籤）；無 CC 時二層備援：`/audio` 低碼率音訊→Gemini 轉錄摘要 → Gemini 直接看影片；bot 端僅為 HTTP 客戶端（`clients/yt_summary.py`，200 秒逾時＋TTL 6 小時快取＋同影片並發去重） |
| 試算表 | `pygsheets` + GCP 服務帳戶 |
| 歌單 | `yt-music-mcp` 微服務（MCP＋REST 雙介面）：載入、快取（TTL 6 小時）、跨歌單搜尋、隨機選歌全在伺服器端；bot 端僅為 HTTP 客戶端（`clients/yt_music.py`），不需 YouTube API Key |
| 排程 | `asyncio` 常駐迴圈（睡到下一分鐘整點再檢查，避免固定間隔累積漂移而跳過整分鐘） |
| 品質 | `ruff` lint＋format（規則釘在 `pyproject.toml`）、`unittest` 單元測試；GitHub Actions 每次 push／PR 全跑 |

---

## ⚠️ 安全注意事項

- 機敏資訊集中於 `.env`（gitignore／dockerignore 皆排除）；GCP 憑證放專案根的 `secrets/`（gitignore 排除、Docker 以唯讀 volume 掛載）。
- **Docker 映像本身不含任何機敏檔案**：金鑰由 `env_file` 於啟動時注入、憑證由 volume 提供。

## 📌 已知限制

- 「吃什麼」清單於**首次使用時載入並快取**，資料異動後需重啟機器人（歌單則由微服務端 TTL 6 小時自動更新，不需重啟）。
- 影片摘要：直播中、`/shorts/`、音樂類（MV/演奏/Topic 頻道）不支援；超過 70 分鐘的影片靜默忽略（不回應）；無 CC 字幕的影片改走音訊轉錄備援（費用略高、耗時約 1 分鐘）。
