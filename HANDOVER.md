# 🤝 AI 助理交接文件（HANDOVER）

> **給主人的使用說明**：新開 session 時，請助理「先完整閱讀專案根目錄的 HANDOVER.md 再開始工作」即可。
> **給接手助理的說明**：正文（一～六節）為**當前現況**，第七節為**歷史紀錄**（凍結不改，新變更往後追加編號）。
> 正文最後更新：2026-08-06。功能與檔案結構的細節以 `README.md` 為準，本文件記錄 README 沒有的：協作共識、跨服務架構、環境雷點、待辦。

---

## 一、專案是什麼（現況）

- **「虎喵小粉絲」**：為遊戲實況主「老虎喵喵喵（虎喵）」粉絲社群（好虎粉）打造的 Discord 互動機器人。
- 功能：混合模式 AI 對話（`!` 指令優先，其餘訊息含圖片/貼圖直達 AI）、YouTube 影片快速摘要（專屬頻道貼連結即觸發）、`!抽`/`!吃`/`!聽`/`!查歌單`/`!心結`、每日 07:30 早安（含全台天氣播報）、每晚 19:30 台灣熱門話題。
- 技術棧：Python 3.14（**uv** 管理版本/venv/套件）＋ discord.py 2.7 ＋ pygsheets；**部署主機就是這台 Windows 機器**（Docker Desktop，容器 `tm_discord_bot`，TZ=Asia/Taipei，restart: always）。
- **bot 端零金鑰設計**：LLM 金鑰只在 n8n、YouTube API Key 只在 yt-music-mcp。機敏設定集中 `.env`（不入版控、env_file 啟動注入），非機敏設定在 `tm_discord_bot/config/config.ini`（入版控）。
- Git：remote `https://github.com/po-hsiang/tm_discord_bot`（主人**個人**帳號，私有）；commit 身分經 `~/.gitconfig` 的 `includeIf "gitdir/i:D:/GitPrivate/"` **自動**使用個人身分（po-hsiang / 個人 gmail），不需手動切換。

## 二、與主人的協作共識（務必遵守）

- **語言**：一律臺灣繁體中文。
- **節奏**：一步一步來——每次聚焦一個任務，做完回報再進下一步；**主人點名的範圍才動手**，其餘只提建議。
- **對頻文化**：較大的功能或方向改動，先提方案討論、取得共識（「對頻」）後再實作。
- **完成定義**：實作 → 單元測試通過 → commit → push → 部署（`docker compose up -d --build`）→ 回報。排程/AI 類功能盡量先做一次**真實鏈路實測**再上線。
- **機敏紀律**：push 前確認無機敏資訊；輸出時**永不印出機敏值**（只印欄位名、布林、長度）。主人瀏覽器：Chrome＝個人 GitHub、Edge＝公司 GitHub。
- **觀察期事項**：主人說「先觀察／讓子彈飛」的項目（見第五節）不要擅自動工，可在盤點時提醒。

## 三、跨服務架構——「想改什麼，去哪裡改」

bot 本體只管 Discord 連線與路由，重活在三個外部服務。改錯層是最常見的白工，先查這張表：

| 想改什麼 | 去哪裡改 |
| --- | --- |
| AI 人設、模型、工具、對話記憶 | n8n「TM AI Agent」工作流（id `vlZLOnZI69bLfqXk`，編輯 `http://localhost:5678/workflow/vlZLOnZI69bLfqXk`；原名「Discord AI Agent」，2026-08-10 更名並改為多客戶端共用）；bot 端只是 HTTP 客戶端 `ai_agent_client.py` |
| 早安/晚間話題的內容風格（Prompt） | bot 端 `plugins/remind_system.py`（改完需重建部署） |
| 影片摘要的模型與提詞 | n8n「YouTube 影片快速摘要」工作流（id `t2OrIkAIr29Qws3S`；**存檔即生效**，不用動 bot） |
| 歌單載入/快取/搜尋、影片資訊/字幕/音訊端點 | `yt-music-mcp` 微服務（**另一專案的 Agent 維護**，這邊只提需求） |
| 台灣熱搜來源（`tw_trends_news` 工具） | n8n 端工具（主人另行維護的工作流） |
| 頻道 ID 等非機敏設定 | `config/config.ini`（改完需重建部署） |
| 機敏鍵（token/密鑰/URL） | `.env`（改完 `docker compose up -d` 重建容器即可，不必 --build） |

- **連線拓撲**：bot 容器 → n8n 走 `host.docker.internal:5678`（Header Auth：`X-Webhook-Secret`）；bot → yt-music-mcp 走外部 docker 網路 `ai-net` 以服務名 `http://yt-music-mcp:8765` 直連（該服務只綁宿主 127.0.0.1，host.docker.internal **打不到**）。
- **AI 記憶 session**（n8n Simple Memory，以 channel_id 為 key）：頻道對話＝頻道 ID；早安＝`morning-call`；晚間話題＝`night-trends`。**測試 AI 改動請用隔離 session**（如 `trends-night-test`），不要污染正式記憶。

## 四、環境雷點（仍有效）

1. **程式與 config.ini 都是 `COPY . /app` 進映像**：任何修改都要 `docker compose up -d --build`，單純 restart 無效。
2. **機敏資訊輸出限制**：印出機敏值（即使截斷）會被安全分類器擋下，只印欄位名/布林/長度。
3. **Git Bash 路徑改寫**：`/app/...` 會被改成 `D:/Program Files/Git/app/...`——`docker exec` 時加 `MSYS_NO_PATHCONV=1`。
4. **Windows 主控台 cp950**：跑 Python 腳本印中文請加 `PYTHONIOENCODING=utf-8`；讀寫檔案一律指定 `encoding="utf-8"`。
5. **n8n 公開 API 的 `PUT /workflows`** 會拒絕含未知鍵的 `settings`（400），更新工作流時要過濾到允許的鍵。
6. **編輯檔案前先 Read**：主人可能自己動過檔案（曾因此把頻道 ID 貼成兩倍長）。
7. **`yt-playlist-sorter` 容器是主人的排程服務，勿動。**
8. 模組以 `scripts/` 為根匯入（`from plugins.xxx import ...`）；repo 的 `tests/` 內已示範 `sys.path` 處理方式。

## 五、待辦與觀察項（2026-08-06 現況）

**觀察中（主人指示先不動，可提醒）**
- **AI 呼叫節流**：混合模式下頻道訊息零節流直達 LLM（成本/濫用風險），主人先觀察使用狀況再決定。
- **舊 YouTube API Key**：曾明碼外露的那把 Key 已無任何服務使用，可在 GCP Console 直接刪除（主人自辦）。

**待辦（依價值排序）**
- **n8n 端 `tw_trends_news` 擴充**：熱搜 3→5、頭條 3→5（已擬好交辦 prompt，見第七節補記 17；bot 端不依賴條數，n8n 可獨立上線）。
- **`!重載` 指令**：「吃什麼」清單目前要重啟才會重載。
- **ai_worker 壅塞觀察**：聊天 AI、影片摘要（最長 200 秒）、晚間話題共用 4 執行緒，極端情況會互相排隊。

## 六、測試與部署

- **單元測試**：repo 根目錄 `uv run python -m unittest discover -s tests`（不依賴 .env 與外部服務）。
- **部署**：`docker compose up -d --build`；驗證 `docker logs tm_discord_bot --since 2m` 看到「機器人「…」已上線」。
- **日誌**：全專案使用 `logging`（`main.py` 以 `client.run(..., root_logger=True)` 統一格式），docker logs 內所有訊息含時間戳；背景任務例外會帶 traceback（`logger.exception`）；排程發送成功會記 INFO（可直接稽核 07:30／19:30 是否正常）。容器日誌有輪替上限（compose 的 logging 設定，10MB × 5 檔）。
- **版號慣例**：每次功能 commit 同步遞增 `pyproject.toml` 與 README 頂部徽章的版本號。
- **commit 訊息**（2026-08-11 起）：**Conventional Commits v1.0.0** 風格——`type(scope): 描述`，type 用英文小寫（feat/fix/docs/refactor/test/chore/ci/perf），描述用臺灣繁體中文、簡短有力；**非必要不寫 body**；破壞性變更加 `!`。身分自動為個人。

## 七、歷次改動紀錄（歷史，凍結不改；新變更往後追加編號）

> ⚠️ 補記 1～17 撰寫時的「第四／五／六／七節」指的是**舊版正文**（2026-07-15 版，可在 git 歷史 `e96ddaa` 之前查看），與現行章節無關。內容若與現行正文衝突，以正文為準。

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

18. **（2026-08-06）文件大掃除＋print→logging**：HANDOVER 正文（一～八節）全面重寫為現況（舊版內容見 git 歷史，`e96ddaa` 之前的版本），`project_report.html` 移出版控（2026-07-15 的分析報告快照，內容已全數過時；git 歷史可找回）。`scripts/` 全域 13 處 `print` 改為模組級 `logging`（`getLogger(__name__)`＋warning/error 分級；背景任務例外改 `logger.exception` 帶 traceback），`main.py` 以 `client.run(..., root_logger=True)` 讓全專案 log 統一 discord.py 的時間戳格式。主人指示：AI 呼叫節流與舊 YouTube API Key 的 GCP 清理**先觀察不動**。

19. **（2026-08-07）穩定性三連發**（主人核可的高優先項）：①排程可觀測性——`_run_daily_task` 發送成功後記 `INFO`（任務名＋字元數），docker logs 即可稽核兩個排程，不用翻 Discord；②晚間話題**單次重試**——首次失敗（逾時/瞬斷/空回覆）先 `NIGHT_TRENDS_RETRY_DELAY`＝60 秒緩衝再重打一次（給 n8n/LLM 喘息，主人特別叮囑間隔別太短），仍失敗才靜默跳過；發送在 `_run_daily_task` 只執行一次，重試不會重複貼文；③compose 加 **docker log rotation**（json-file，10MB × 5 檔）。測試 24/24（含新的重試成功/重試仍失敗案例，`time.sleep` 已 mock 不會真等 60 秒）。同回合亦向主人說明 GitHub Actions CI 對個人帳號的影響範圍，等主人核可後另行上線。

20. **（2026-08-07）CI 上線＋按鈕投票淘汰賽原型**：①**GitHub Actions CI**（`.github/workflows/ci.yml`：push/PR/手動觸發，setup-uv → `uv sync --frozen` → unittest；測試不依賴 .env 故無需任何 GitHub secret，push 前已本機模擬「無 .env」環境驗證）——第五節待辦的 CI 項目完成。②**`!投票賽` 原型**（`plugins/vote_tournament.py`）：8 強按鈕投票淘汰賽——discord.ui 按鈕、全頻道一人一票（ephemeral 回覆、開票前保密、可改票）、每輪 30 秒最高票晉級、平手/無人投票隨機（「貓咪擲硬幣」）；**僅測試頻道啟用**（main.py 以 `test_channel_id` 守門），試玩參數 `BRACKET_SIZE`／`ROUND_SECONDS` 在模組頂部，正式上線與否等主人試玩後對頻；與 `!21` 打字版並存。純邏輯（計票/晉級/輪次名）與 Discord UI 分離，`tests/test_vote_tournament.py` 9 個測試。③創意清單其餘決議：開台通知不做（主人已有第三方）；`tw_weather` 工具交辦提詞已擬給主人轉交 n8n 端 Agent（中央氣象署 F-C0032-001、輸入縣市選填、需主人註冊免費授權碼），工具上線後 bot 端再調整早安 Prompt 播報天氣。

21. **（2026-08-10）n8n AI Agent webhook 路徑遷移**：n8n 端工作流更名「Discord AI Agent」→「**TM AI Agent**」（改為多客戶端共用，id 不變 `vlZLOnZI69bLfqXk`），webhook 路徑 `discord-ai-agent` → `tm-ai-agent`（舊路徑已 404）。bot 端只改 `.env` 的 `N8N_AGENT_WEBHOOK_URL`（密鑰與 request/response 契約完全不變），`docker compose up -d` 重建後於**容器內**以 `AIAgentClient` 實測新路徑（隔離 session `url-migration-test`）確認 AI 正常回覆。`.env.example`、README、HANDOVER 第三節、client docstring 的名稱已同步。

22. **（2026-08-10）`!投票賽` 轉正＋早安加天氣播報**：①主人於測試頻道試玩 `!投票賽` 後核可**轉正**——main.py 移除 `test_channel_id` 守門（助手/測試頻道皆可玩），賽制維持 8 強、每輪 30 秒；一次只開一場（跨頻道共用 `is_running`，同 `!21` 的既知限制）。②n8n 端 `tw_weather` 工具已由主人上線（縣市全名選填、未指定預設全台總覽、「台/臺」有正規化）——實測全台總覽約 8 秒、指定縣市約 4 秒，遠低於預設 60 秒逾時故**早安不需逾時覆寫**；早安 Prompt 加入天氣播報指示（一兩句重點＋貼心提醒、自然融入不像制式氣象報告、**取不到就略過照常打招呼**的降級指示），全篇字數 60→約 100 字元。已用隔離 session（`weather-test`／`morning-test`）以正式 Prompt 原文實測，產出格式命中。第五節的投票賽試玩與 tw_weather 兩項待辦自此結案。

23. **（2026-08-10）兩套淘汰賽全數移除**（主人指示：Discord Bot 不需要此功能，讓專案乾淨一些）：`!21` 打字版（`two_choices_one_system.py`）與 `!投票賽` 按鈕版（`vote_tournament.py`，補記 20/22 剛上線旋即下架）連同 `tests/test_vote_tournament.py` 一併刪除，git 歷史可找回。連帶清理：`auto_reply_system.py` 不再需要注入 `what_to_eat`（原僅供淘汰賽候選清單），建構子簡化；`main.py` 移除遊戲路由——非指令訊息現在**直接**進 AI 對話（原本會先檢查淘汰賽的左/右輸入）。第五節「淘汰賽 per-channel 狀態」待辦一併結案。README 的混合模式說明、指令表、結構樹、已知限制同步更新。

## 八、開場動作建議

1. 讀 `README.md`（功能與結構）與本檔正文（共識、架構對照、雷點、待辦）。
2. `git status` 確認工作區乾淨；`uv run python -m unittest discover -s tests` 確認測試全綠。
3. `docker ps`＋`docker logs tm_discord_bot --since 24h` 檢查容器健康與兩個排程（07:30 早安、19:30 晚間話題）是否正常發送。
4. 向主人回報就緒，等待點名任務（可順帶提醒第五節的觀察項與待辦）。
