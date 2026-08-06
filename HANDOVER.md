# 🤝 AI 助理交接 Prompt（HANDOVER）

> **給主人的使用說明**：專案搬移至 `D:\GitPrivate\tm_discord_bot` 並重開 Claude Code session 後，
> 將本檔**全文複製貼上**作為第一則訊息；或直接輸入「請先完整閱讀專案根目錄的 HANDOVER.md 再開始工作」。
> 本文件由前一個 session 的 Claude Code 於 2026-07-15 撰寫。

---

你是接手 `tm_discord_bot` 專案的 AI 助理。前一位助理已與主人合作完成數項任務，以下是完整交接內容，請仔細閱讀並遵循其中的共識與教訓，接續未完成的工作。

## 一、專案是什麼

- **「虎喵小粉絲」**：為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群（好虎粉）打造的 Discord 互動機器人。
- 功能：ChatGPT 人設問答（`!問`/`!gpt`）、搜圖（`!搜圖`，已失效）、抽籤（`!抽`）、吃什麼（`!吃`）、YouTube 點歌（`!聽` 等）、查歌單（`!查歌單`）、二選一淘汰賽（`!21`）、每日 07:30 GPT 早安。
- 技術棧：Python 3.8（Poetry）＋ discord.py 2.3 ＋ openai 0.27（舊版 SDK）＋ pygsheets ＋ YouTube Data API v3；Docker Compose 部署（TZ=Asia/Taipei、restart: always）。
- 約 14 個 Python 檔、780 行。進入點 `tm_discord_bot/scripts/main.py`，模組匯入以 `scripts/` 為根（執行時的工作目錄有講究，見 README）。
- 機敏設定集中在 `tm_discord_bot/json/config.json`（10 個欄位：discord_bot_token、openai_api_key、openai_model、google_credential_file、what_to_eat_url、youtube_developer_key、my_yt_music_playlist_id、assistant/chitchat/test_channel_id）＋ GCP 服務帳戶憑證 JSON。`.gitignore` 以 `*.json` 全部擋掉，未入版控。
- Git remote：`https://github.com/po-hsiang/tm_discord_bot.git`（主人的**個人** GitHub 帳號）。

## 二、前一個 session 已完成的工作

1. **全案掃描與分析**（未動任何既有程式邏輯）。
2. **重寫 `README.md`**：功能指令表、專案結構、config.json 欄位說明、`.env` 設定步驟、Poetry／Docker 啟動方式、安全注意事項、已知限制。
3. **產出 `project_report.html`**：自包含（無外部資源）的分析報告，含 4 張手繪 SVG（系統架構圖、on_message 流程圖、早安排程流程圖、部署流程圖）、模組/指令一覽、**20 項問題清單（高/中/低分級）**、深淺色主題切換。注意：報告是 `.env` 修正**之前**的快照，其中問題 #1（寫死金鑰）已修復。
4. **修復問題 #1 — 寫死的 Google API Key**（原在 `youtube_handler.py:13` 明碼）：
   - 新增 `.env`（存放 `YOUTUBE_API_KEY`，已加入 `.gitignore` 與 `.dockerignore`）與 `.env.example`（範本，入版控）。
   - `tm_discord_bot/utils/config_utils.py` 匯入時 `load_dotenv(專案根/.env)` —— 這是集中載入點，日後 config.json 的其他機敏資訊也循此遷移。
   - `youtube_handler.py` 改 `os.getenv("YOUTUBE_API_KEY")`，缺值時拋 `RuntimeError`（含中文指引）。
   - `python-dotenv = "^1.0"` 已寫入 pyproject.toml 與 poetry.lock，並已裝進 `.venv`。
   - 已端對端驗證：金鑰載入成功（長度 39）、缺值防呆正常、grep 全案無 `AIzaSy` 殘留。
5. **Git 身分調查**（詳見第六節）。

## 三、與主人的協作共識（務必遵守）

- **語言**：一律使用臺灣繁體中文交流與撰寫文件。
- **節奏**：主人明確喜歡「**一步一步來**」——每次聚焦一個小任務，做完回報再進下一步，不要自作主張擴大範圍。
- **修改權限**：第一輪任務曾要求「不異動任何程式碼」；之後已授權修改（.env 隔離任務）。原則：**主人點名的範圍才動手**，其餘只提建議。
- **問題處理順序共識**：安全（金鑰）→ 穩定性（事件迴圈阻塞、啟動脆弱）→ 架構（重複實例、config 統一）→ 品質（logging、測試）。
- **git 身分切換**：已提供方案但**主人尚未決定**，不要擅自更改任何 git config。

## 四、踩過的雷與必須傳承的經驗（環境陷阱）

1. **Git dubious ownership**：舊路徑資料夾的 Windows 擁有者 SID 與目前使用者不同，git 指令會失敗。解法：以 `git -c safe.directory="<repo路徑>" <指令>` 內聯繞過（不落地全域設定）。搬到 `D:\GitPrivate` 後若再出現，同樣處理或建議主人執行 `git config --global --add safe.directory D:/GitPrivate/tm_discord_bot`。
2. **⚠️ 工作區有大量「未 commit 的historical 工作」**：最後一次 commit 是 **2024-02-08**，此後 `compose.yaml`、`openai_api.py`、`remind_system.py`、`pyproject.toml`、`poetry.lock` 的修改與多個新檔（`youtube_handler.py`、`analyzer.py`、`video analysis.py`、`utils/`、`config/`）都**只存在於工作區**。**絕對不要 `git checkout`/`git reset` 這些檔案**，會毀掉兩年多的未提交工作。
3. **機敏資訊輸出限制**：印出 config.json 的值（即使截斷）會被安全分類器擋下。只印**欄位名稱**、布林值或長度，永遠不要印憑證內容。
4. **`poetry run python` 在 Git Bash 下會靜默無輸出**（原因不明）——改直接呼叫 `./.venv/Scripts/python.exe`。
5. **搬家後 `.venv` 大概率會壞**（venv 內含絕對路徑）：在新路徑先跑 `poetry install` 重建，不要直接沿用。
6. **系統 Python（C:\Python38，3.8.5）沒有專案相依套件**（如 youtube_transcript_api），測試務必用專案 `.venv`。
7. **檔名地雷**：`plugins/video analysis.py` 檔名含空格，shell 迴圈與 import 都會炸，處理檔案清單時記得加引號。
8. **Windows 主控台 cp950**：Python 印中文可能變亂碼（僅顯示問題，邏輯不受影響）；讀寫檔案一律明確指定 `encoding="utf-8"`。
9. **Browser 面板開 `file://` 頁面需逐次核准**，無法直接截圖驗證 —— 改用程式做 HTML 結構驗證（標籤配對、SVG 數量）。
10. **`poetry add --lock` 只更新 lock 不安裝**，之後要 `poetry install --no-root` 才會進 venv。

## 五、未完成的待辦（依共識的優先順序）

完整 20 項清單見 `project_report.html` 第 07 節，以下是尚未處理的重點：

- **（主人自辦，可提醒）** 到 GCP Console 重新產生曾明碼外露的 YouTube API Key 並加 API 限制，更新至 `.env`。
- **（建議下一步）版控整理**：金鑰已移除，可以協助主人規劃將累積的修改分批 commit。
- **高 #2**：OpenAI 同步呼叫（含 `time.sleep` 重試）在 async 事件內執行會凍結整個事件迴圈 → `asyncio.to_thread()` 或升級 openai ≥1.0 用 AsyncOpenAI。
- **高 #3**：啟動時同步抓試算表＋整份歌單，外部服務故障就起不來，配 `restart: always` 會無限重啟 → 延遲載入＋失敗降級。
- **高 #4**：`scripts/config_utils.py` 開檔未指定 utf-8；讀檔失敗回傳 None 造成後續 AttributeError → fail-fast。
- **高 #5**：早安背景任務例外後靜默死亡 → try/except＋log 或改 `discord.ext.tasks`。
- **中**：重複實例化（main 與 AutoReplySystem 各建一套，歌單抓兩次、GPT 歷史不同步）→ 依賴注入；輪詢漂移；淘汰賽全域共用狀態；資料只在啟動載入；Python 3.8 EOL＋openai 0.27 升級；`!查歌單` 用 `[5:]` 切字會吃字；`!搜圖` 依賴的 source.unsplash.com 已停業；兩份重複的 config_utils。
- **低**：analyzer.py 引用未定義變數無法執行、video analysis.py 檔名空格（開發中程式碼建議移出主線）；print → logging；tests/ 掛零＋無 CI；Docker 映像含金鑰 JSON（改 env/volume）；魔術數字集中管理。
- **可選**：把 config.json 其他機敏值（discord token、openai key）也遷入 `.env`（載入點已備好）。

## 六、Git 身分現況（主人尚未決定，只可建議不可動手）

- 全域：`pohsiangjuan` /（**公司信箱**，略）；此 repo 無 local 覆寫。
- 矛盾點：commit 掛公司 email，卻推到個人帳號 po-hsiang 的 GitHub → 貢獻牆可能不計入。
- 認證：HTTPS ＋ Git Credential Manager（`credential.helper = manager`）；`~/.ssh/config` 沒有 GitHub 別名（現有的是公司伺服器跳板設定，勿動）。
- 已提供的方案：① repo 內 `git config user.name/email` 手動切；② `~/.gitconfig` 用 `includeIf "gitdir/i:D:/GitPrivate/"` 自動切個人身分（搬家後路徑正好適合）；③ 推送認證用 remote URL 帶帳號（`https://po-hsiang@github.com/...`）或 SSH 別名。

## 七、當前檔案結構（搬家後根目錄為 D:\GitPrivate\tm_discord_bot）

```
tm_discord_bot/
├── .env                ← 新增（機敏，git/docker 皆忽略；內含 YOUTUBE_API_KEY）
├── .env.example        ← 新增（範本，入版控）
├── .gitignore          ← 已加 .env
├── .dockerignore       ← 已加 .env
├── HANDOVER.md         ← 本交接文件
├── README.md           ← 本次重寫
├── project_report.html ← 本次新增（分析報告，含 20 項問題清單）
├── Dockerfile / compose.yaml
├── pyproject.toml / poetry.lock  ← 已加 python-dotenv ^1.0
├── .venv/              ← 搬家後需 poetry install 重建
└── tm_discord_bot/
    ├── config/config.ini          （youtube api url 等非機敏設定）
    ├── json/                      （config.json＋GCP 憑證，不入版控）
    ├── scripts/
    │   ├── main.py                （進入點）
    │   ├── config_utils.py        （待修：無 utf-8、回傳 None）
    │   ├── google_sheet_utils.py
    │   └── plugins/               （8 個運作中模組＋3 個開發中：youtube_handler、
    │                                analyzer（損壞）、video analysis.py（檔名含空格））
    └── utils/config_utils.py      ← 已改：匯入時 load_dotenv(專案根/.env)
```

## 補記（2026-07-15，接手 session 更新）

> ⚠️ 本節之後的內容若與此補記衝突，以補記為準。

1. **已全面改用 uv 管理**（取代 Poetry）：`pyproject.toml` 改為 PEP 621 格式、新增 `uv.lock` 與 `.python-version`（釘 3.8）、`poetry.lock` 已移除、Dockerfile 改用 uv 建置、README 同步更新。本文件中所有 `poetry ...` 指令請改用 `uv sync` / `uv run python ...`。第四節第 4、10 點的 Poetry 雷點已不適用；**`uv run` 在 Git Bash 下輸出正常**（已驗證）。
2. **搬家後 `.git` 資料夾不在新路徑**：`D:\GitPrivate\tm_discord_bot` 目前不是 git 倉庫（推測搬移時未複製 `.git`，舊路徑可能仍保有完整歷史）。第四節第 1、2 點與第六節的 git 事項，需等主人把 `.git` 搬回或說明處理方式後才能進行。
3. `.venv` 已在新路徑以 `uv sync` 重建（Python 3.8.5，來自 C:\Python38），匯入煙霧測試、`.env` 載入（金鑰長度 39）、全案 byte-compile 皆通過。
4. **（2026-07-31 更新）2023–2024 舊歷史已從 GitHub 救回**：搬遷時遺失的只是本機 `.git`，遠端 `po-hsiang/tm_discord_bot`（私有）仍保存 2023-05-11～2024-02-08 共 18 個 commit。已將本地重建的歷史「嫁接」其上（快照樹逐位元組不變、fast-forward 推送、未使用 force），本地分支改名 `main` 對齊遠端，現與遠端完全同步。第四節第 2 點的「未提交工作」警語已成歷史——一切都在版控與遠端備份中了。推送前已以真實機敏值比對全歷史 110 個 blob：僅模型名稱誤中，金鑰零外洩，`.env`／`config.json`／GCP 憑證從未被追蹤。原先記載：已 `git init` 並建立基線 commit（`fc34bc9`，嫁接後為 `98cefbb`）。**第六節的 git 身分議題已解決**：主人採方案 ②，`~/.gitconfig` 以 `includeIf "gitdir/i:D:/GitPrivate/"` 引入 `~/.gitconfig-personal`（po-hsiang / 個人 gmail），本 repo 全部 commit 皆為個人身分；另 `credential.useHttpPath = true` 的區段名已修正為 `[credential "https://github.com"]`（原本缺 `https://` 不會生效）。尚未設定 remote、未推送。
5. **第五節的高優先 #2／#3／#4／#5 已全部修復**（commit `a432429`、`0649858`）：config fail-fast＋utf-8、阻塞呼叫移至單執行緒 worker（Python 3.8 用 run_in_executor）、歌單與吃什麼清單延遲載入＋失敗降級＋on_ready 背景預載、早安任務 try/except 防呆。AutoReplySystem 已支援注入共用實例（main.py 傳入），歌單不再抓兩次。
6. **中優先四項已修復並部署**（commit `8d46f76`，2026-07-16）：GPT 對話歷史污染（重試/失敗零殘留、成對裁剪、早安改走 `ask_question_without_memory`）、`!查歌單` 切字吃字、排程輪詢漂移（睡到分鐘整點）、指令參數防呆（`!抽` 帶參數、`!問`/`!搜圖` 空參數）。**部署主機就是這台 Windows 機器**（Docker Desktop，容器 `tm_discord_bot`），已以新映像重建並確認上線（discord.py 2.7.1 連線正常、PYTHONUNBUFFERED 已加，docker logs 即時可見）。主人已表示 YouTube API Key 暫不更換（專案未分享過）。剩餘待辦：資料刷新機制、淘汰賽 per-channel、Python/openai 升級、config 整併、`!搜圖` 處置、logging、測試等中低優先項目。

7. **（2026-07-31）AI 功能已抽離為 n8n 微服務**：`!問`/`!gpt`（含圖片/貼圖）與每日早安改走 n8n「Discord AI Agent」工作流（Gemini 3.5 Flash＋人設＋工具＋按頻道 Simple Memory，早安用獨立 `morning-call` session）。bot 端新增 `plugins/ai_agent_client.py`（Header Auth、60 秒逾時、失敗降級），AI 指令走獨立 4 執行緒池不卡原生指令。`openai_api.py` 與 openai 套件已退役、`!搜圖` 指令已移除。webhook 已加 Header Auth（密鑰在 `.env` 的 `N8N_WEBHOOK_SECRET`；ngrok 公開網址不再裸奔）。bot 容器經 `host.docker.internal` 直連宿主機 n8n，機敏環境變數由 compose `env_file` 注入。**雷點**：n8n 公開 API 的 `PUT /workflows` 會拒絕含未知鍵的 `settings`（400），更新工作流時要過濾到允許的鍵。

8. **（2026-07-31）設定整併＋AI 自由對話頻道**：`config.json` 退役（本機留有 `json/config.backup.json` 備份，gitignore 排除）——機敏值全數遷入 `.env`（`DISCORD_BOT_TOKEN`／`YOUTUBE_API_KEY`／`GOOGLE_CREDENTIAL_FILE`／`WHAT_TO_EAT_URL`＋n8n 三鍵），非機敏設定（各頻道 ID、歌單 ID）入版控的 `config/config.ini`；`scripts/config_utils.py` 為唯一讀取器（回傳鍵與舊 config.json 相容）。三個開發中模組（youtube_handler／analyzer／video analysis.py）與 `utils/config_utils.py` 已移除（git 歷史可找回）。Docker 映像不再含機敏檔（env_file 注入＋json/ 唯讀 volume）。新功能：`config.ini` 的 `ai_chat_channel_id`／`ai_chat_test_channel_id` 指定的頻道為**免指令 AI 自由對話頻道**（文字/圖片/貼圖直達 agent、回覆形式回應、忽略其他 bot；留空停用）——**主人填入頻道 ID 後需 `docker compose up -d --build` 重新部署**。第七節的檔案結構已過時，以 README 為準。

9. **（2026-07-31）Python 3.8 → 3.14**：`.python-version`＝3.14、`requires-python = ">=3.14"`、Dockerfile 改 `python:3.14-slim`；uv 重新解析後 discord.py 2.7.1 原地支援、aiohttp 升 3.14.1、dotenv 升 1.2.2。google-auth 的 3.8 EOL 警告從此消失。本機 `.venv` 為 uv 管理的 CPython 3.14.2（系統的 C:\Python38 已不再使用）。第四節第 6 點（系統 Python 3.8.5）已過時。

10. **（2026-08-01）混合對話模式＋歌單改接 yt-music-mcp 微服務**：助手／測試頻道改為「`!` 開頭走指令 → 淘汰賽進行中的左右鍵走遊戲 → 其餘訊息（含純圖片/貼圖）一律自然語言直達 AI」；`!問`/`!gpt` 退役（打了會回轉換提示），前一輪的獨立 AI 頻道機制（ai_chat_*）也移除。歌單功能（`!聽`/`!查歌單`/早安選歌）改打主人自建的 `yt-music-mcp` 微服務（MCP＋REST，快取 TTL 6h，`/random`、`/search` 跨 13 個歌單）——bot 端為 `plugins/song_picker.py`，`youtube_api.py` 與 youtube-transcript-api 相依已移除，**bot 不再需要 YouTube API Key**（.env 的 `YOUTUBE_API_KEY` 已無人讀取）。連線方式：bot 容器加入外部 docker 網路 `ai-net`，以服務名 `http://yt-music-mcp:8765` 直連（該服務只綁宿主機 127.0.0.1，host.docker.internal 打不到）。config.ini 精簡為 [discord] 三鍵。

11. **（2026-08-04）YouTube 影片快速摘要功能上線**（規格源自舊 LINE bot 的 `NEW_FREATURES_quick_summary.md`，未入版控）：專屬頻道（`config.ini` 的 `video_summary_channel_id`）或測試頻道貼 YouTube 連結（`watch?v=`/`youtu.be`/`/live/` 三格式）即觸發，⏳ reaction → Embed 回覆「重點大綱」2～5 點。三層分工：bot（`plugins/video_summary.py`，⏳/Embed/6h TTL 快取/同影片並發去重 `video_id→Future`）→ n8n「YouTube 影片快速摘要」工作流（id `t2OrIkAIr29Qws3S`，Gemini Flash 結構化輸出；**模型與提詞都在這裡改**，改完存檔即生效）→ yt-music-mcp 新端點 `GET /video/{id}`（1 unit）與 `GET /transcript/{id}`（免配額；人工字幕優先→自動生成）。回應契約：`{ok, video_id, title, channel, thumbnail_url, video_url, duration_seconds, summary:{重點大綱:[...]}}`，錯誤碼 `VIDEO_NOT_FOUND`/`LIVE_STREAM`/`NO_TRANSCRIPT`/`SUMMARY_FAILED`/`UPSTREAM_ERROR` 對應文案在 plugin 的 `ERROR_MESSAGES`。新 env 鍵 `N8N_YT_SUMMARY_WEBHOOK_URL`（沿用 `N8N_WEBHOOK_SECRET`）。`tests/test_video_summary.py` 為本 repo 首批單元測試（`uv run python -m unittest discover -s tests`）。**雷點**：`config.ini` 與程式碼都是 `COPY . /app` 進映像，任何修改都要 `docker compose up -d --build`（單純 restart 無效）。已知限制：無 CC 字幕（含字幕燒在畫面內）的影片無法摘要，Phase 2 候選方案為 n8n 端 fallback 讓 Gemini 直接吃 YouTube URL 看影片（bot 端零改動）。

12. **（2026-08-04）無字幕影片二層備援＋短期成本追蹤報告**：n8n workflow「YouTube 影片快速摘要」的 NO_TRANSCRIPT 分支改為——音樂閘門（標題關鍵字/「 - Topic」頻道→`MUSIC_CONTENT`）→ 時長閘門（>7200 秒→`VIDEO_TOO_LONG`）→ **音訊備援**（yt-music-mcp 新端點 `GET /audio/{id}`：yt-dlp 抽 OGG/Opus 32kbps mono → Gemini Files API 上傳 → 轉錄＋摘要，實測 20 分鐘影片全程約 54 秒、36.8k audio tokens）→ 技術性失敗才走**影片備援**（Gemini 直接吃 YouTube URL，MEDIA_RESOLUTION_LOW）。bot 端已補兩個錯誤文案。**目前模型配置**：CC 路徑＝OpenAI `gpt-5.6-luna`（credential「My Dev」）、備援兩層＝`gemini-3.1-flash-lite`（credential「部門 Gemini API」）。回應多了 `source`（transcript/audio/video）與 `stats`（逐字稿字數/token 用量/模型；stats 是本 session 經 API 直改 4 個 code 節點加上的，備份在當日 scratchpad）。**成本追蹤（短期功能）**：`plugins/summary_report.py` 在每次實際分析後把「影片/片長/字幕/逐字稿字數/結果/Input Tokens/預估 NT$」追加到 `reports/video_summary_report.html`（gitignore 排除、compose 掛 `./reports:/app/reports` volume 持久化；快取命中不記）；**計價常數（模型單價/匯率）寫在該模組開頭，換模型記得同步調整**；不想追蹤時移除 video_summary.py 內的 append_record 呼叫即可。**待整理**：workflow 內有一組上一輪迭代殘留的無入口節點（備援閘門/取音訊/檢查音訊/上傳啟動/上傳音訊/檢查上傳/音訊摘要/準備影片摘要/影片摘要），永遠不會執行、僅視覺干擾，主人同意後可刪。

13. **（2026-08-05）時長閘門收緊＋逾時階梯定案**（主人拍板）：影片摘要的時長上限收為 **70 分鐘（4200 秒）**，且閘門移至 n8n 主路徑（不分有無 CC 一律擋）；超長影片 **bot 端靜默處理**——不回覆、只撤 ⏳（`video_summary.py` 的 `SILENT_ERROR_CODES` 機制，成本報告仍記一列）。逾時階梯：**bot 200 秒（`N8N_YT_SUMMARY_TIMEOUT` 預設值）＞ n8n 全流程目標 190 秒 ＞ yt-music-mcp 音訊抽取 180 秒**——上游比下游寬，留封包與排隊餘裕；後兩層由各自專案的 Agent 維護。

14. **（2026-08-05）摘要新增影片標籤**：n8n 端改版摘要風格（重點 2～4 點、每點 34 字內、活網仔口吻）並新增 `summary.影片標籤`（單行字串如「#魟魚 #單性生殖」，選填）；bot 端 `build_embed()` 把標籤放在重點條列下方（空一行），欄位缺漏時自動略過、完全相容舊格式。

15. **（2026-08-05）成本追蹤報告已拆除**（短期觀察結束，主人指示）：`plugins/summary_report.py`、其測試、compose 的 `./reports` volume、summarize() 掛鉤與錯誤路徑的 stats 透傳皆已移除；補記 12 的相關描述自此失效。歷史報告檔仍留在本機 `reports/video_summary_report.html`（gitignore/dockerignore 續留 `reports/` 條目防誤收）。n8n 端回應的 `stats` 欄位仍在（上游忽略未知欄位、無害，日後要觀察成本可直接復用）；該 workflow 內 9 個執行不到的殘留節點已由 n8n Agent 清除（2026-08-05 驗證：38 節點全數可達、無懸空連線、webhook 實測正常）。

16. **（2026-08-05）每晚 22:00 台灣熱門話題推播**：`RemindSystem` 新增第二個每日任務——經 n8n AI Agent 呼叫主人另行開發的工具 `tw_trends_news`（台灣 Google 熱搜前 3 名含搜尋量與相關新聞＋頭條前 3 條）取得時事，整理成閒聊話題發到 `chitchat_channel_id`。**政治過濾走 bot 端 Prompt、n8n 端不動**（對頻共識：工具保持通用）——排除政治與兇殺/輕生等悲劇社會案件、正向清單（娛樂/遊戲/動漫/科技/生活/體育優先）、無料時自起輕鬆話題替代；實測 Gemini 依此正確跳過國際政治與悲傷新聞。獨立 `night-trends` 記憶 session（與 morning-call 同招，讓連續幾晚內容有變化）。實作面：早安與晚間話題共用新抽出的 `_run_daily_task()` 通用每日迴圈（builder 回傳 None＝本次靜默跳過——晚間話題屬錦上添花，AI 故障時不在閒聊頻道貼降級訊息；早安維持原本會貼降級文字的行為）；`ai_agent_client.ask()` 新增可選 `timeout` 覆寫（晚間話題 120 秒＝`NIGHT_TRENDS_TIMEOUT`，工具抓取較慢）。新增 `tests/test_remind_system.py`（7 測試，不依賴 .env）。

17. **（2026-08-06）晚間話題改版**（首播成功後主人回饋）：時間 22:00 → **19:30**（與早安 07:30 恰隔 12 小時）；Prompt 改版——去開場白與結尾互動邀請、第一行一句話總結今晚熱搜氛圍＋每話題一行 emoji 條列（2～4 個）、語氣改鄉民/活網仔（不低俗不嘲諷）、全篇 150 字內。已用隔離 session（`trends-night-test`）實測新 Prompt，產出命中理想格式。另擬請 n8n 專案的 Agent 把 `tw_trends_news` 擴充為熱搜前 5＋頭條前 5（bot 端 Prompt 只挑 2～4 個、不依賴條數，n8n 端可獨立擇期上線）。

## 八、開場動作建議

1. 先確認新路徑下 git 可用（dubious ownership）與 `.venv` 是否需重建。
2. 用 `git -c safe.directory=... status --short` 對照第四節第 2 點，確認未提交工作完好。
3. 向主人回報你已讀完交接文件，詢問要從第五節哪一項開始（依共識預設建議：版控整理或高優先 #2）。
