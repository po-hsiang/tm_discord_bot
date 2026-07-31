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

## 八、開場動作建議

1. 先確認新路徑下 git 可用（dubious ownership）與 `.venv` 是否需重建。
2. 用 `git -c safe.directory=... status --short` 對照第四節第 2 點，確認未提交工作完好。
3. 向主人回報你已讀完交接文件，詢問要從第五節哪一項開始（依共識預設建議：版控整理或高優先 #2）。
