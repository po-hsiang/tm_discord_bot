# 封存：Google Maps 評論摘要

| 項目 | 內容 |
| --- | --- |
| 狀態 | **已下架封存**（2026-08-19） |
| 試營運期間 | 2026-08-17 ～ 2026-08-19（僅測試頻道） |
| 功能完整的最後版本 | `v0.5.4` — git tag **`archive/maps-review`**（commit `c83eb52`） |
| 下架原因 | 上游資料量不足導致成功率過低，**不是實作缺陷** |
| 解封條件 | Places API (New) 的 `reviewSummary` 欄位開放臺灣／中文 |

> 這份文件的目的不是保存程式碼（那在 git 裡），而是保存**查證結果**。
> 程式碼半天能重寫，底下的 API 能力邊界、條款限制與實測數據花了一整個下午。
> 日後要復活這個功能，**先讀第 2、4 節**再動手。

---

## 1. 這功能原本做什麼

使用者在頻道貼上 Google 地圖連結 → 機器人回一張卡片，內含評分、評論則數、
好評／負評條列、樣本大小提醒與逐筆來源連結。

```
使用者貼連結
  → bot 路由 classify() 判定 ROUTE_MAPS
  → POST n8n /webhook/maps-review（header X-Webhook-Secret）
      → Maps Grounding Lite Resolution API 把短網址解析成 place ID
      → Gemini 以 google_maps 工具 grounding，產出摘要與 place_citation
  → bot 驗證契約 → 組 Discord Embed
```

**意圖分流**（刻意做成確定性規則，不去猜那句話是不是問句）：
訊息扣掉連結只剩空白與標點 → 直接回卡片；連結旁邊有話 → 交給 AI Agent 對話，
由它自行決定要不要呼叫 n8n 端的 `maps_review` 工具。

### n8n → bot 的回應契約

```jsonc
{
  "place":   { "name", "address", "maps_uri", "rating", "rating_count" },
  "review":  { "verdict", "positive": [...], "negative": [...], "caveat" },
  "facts":   { "yes": [...], "no": [...], "price_level" },
  "sources": [ { "title", "uri" }, ... ],
  "error_code": "..."   // 僅失敗時
}
```

錯誤碼：`URL_UNRESOLVED`、`NOT_A_PLACE`、`NO_REVIEW_DATA`、`MISSING_SOURCES`、
`SUMMARY_FAILED`、`UPSTREAM_ERROR`。

**`facts` 的鐵則（若復活務必沿用）**：`yes` ＝確定有、`no` ＝確定沒有、
**沒被列到 ＝ Google 沒登錄資料**。Places API 對不知道的屬性是整個欄位不回傳，
所以「沒出現」不等於「沒有」——**永遠不要從缺漏推論出「沒有 XX」**。

---

## 2. 為什麼下架（實測數據）

Google 對 Maps grounding 的行銷用語是「insights from millions of user reviews」。
**那句話描述的是語料庫規模，不是單次查詢能取回的評論數。** 實測：

| 店家 | Google 上的評論總數 | 實際撈到的評論 |
| --- | --- | --- |
| Klatch Coffee（板橋） | 649 則 | 3 次查詢各只回 **1 則**評論引用 |
| 洋朵義式廚坊（板橋） | 2,933 則 | 約 **3/4 的機率直接回 `NO_REVIEW_DATA`** |

於是使用者實際看到的畫面，多半是這兩句：

```
這個地點的評論太少，整理不出可靠的心得 🙏
小粉絲的 AI 大腦暫時連不上線，請稍後再試 🙏
```

單次回應耗時 30～62 秒，還會佔用 `ai_worker` 執行緒池（共 4 條，與對話 AI、
影片摘要、晚間話題共用）。**問得越多、失敗回應越多、越擾民** —— 這是下架的直接原因。

曾經嘗試但無法解決的方向：
- 摘要階段重試一次（n8n 端已實作，救回過洋朵一次，但沒有改變整體成功率）
- 提詞變體、解析重試 —— 皆已否決，問題在檢索端不在生成端
- grounding 無法指定 place ID 鎖定目標（只能給經緯度，店名寫在提詞裡）

---

## 3. 查證紀錄（2026-08-17 對照官方文件）

> 以下數據與限制皆為**當時**的官方文件內容，復活前必須重新核對。

### 為什麼走 grounding 而不是 Places API 的 `reviews` 欄位

| | Places API `reviews` | Grounding with Google Maps |
| --- | --- | --- |
| 取得的評論量 | **最多 5 則**，按關聯性排序，**無排序參數** | Google 端檢索（實測約 1 則，見第 2 節） |
| 計價 | Place Details **Enterprise + Atmosphere**：月免費 1,000，之後 **$25／1,000** | 月免費 5,000，之後 **$14／1,000** |
| 短網址解析 | 不支援 | Maps Grounding Lite Resolution API **官方支援** `maps.app.goo.gl` |
| 條款 | 禁止 pre-fetch／cache／store（place ID 例外，可永久保存） | 有明文開給 LLM grounding 的例外條款 |

當初選 grounding 是**基於文件的正確判斷**（更便宜、支援短網址、條款明確允許）；
錯的是相信了「millions of user reviews」這句行銷語會反映在單次檢索量上。

### Places API (New) 相關計價（每月免費額度／超出後每 1,000 次）

| SKU | 免費 | 單價 |
| --- | --- | --- |
| Place Details Essentials | 10,000 | $5 |
| Place Details Pro | 5,000 | $17 |
| Place Details Enterprise | 1,000 | $20 |
| Place Details Enterprise + Atmosphere（含 `reviews`、`reviewSummary`） | 1,000 | $25 |
| Text Search Pro | 5,000 | $32 |

**混合 field mask 以最高階 SKU 計價** —— 要 `reviews` 就等於整筆都用最貴的價錢。

### Maps Grounding Lite Resolution API（解析分享短網址）

```http
POST https://mapstools.googleapis.com/v1alpha:resolveMapsUrls
X-Goog-Api-Key: <key>          # 或 ?key=<key>

{ "urls": ["https://maps.app.goo.gl/..."] }   // 上限 20 筆
```

回應 `{"entities":[{"place":"places/ChIJ..."}], "failedRequests":{"0":{"code":3,"message":"Invalid URL."}}}`。
免費、600 QPM，但當時**仍是 experimental（pre-GA）**。

### Grounding with Google Maps（Gemini API）

```jsonc
"tools": [ { "type": "google_maps", "latitude": 25.0, "longitude": 121.5 } ]
```

只有這三個欄位，**無法用 place ID 鎖定地點**（要靠提詞寫店名）。
回應帶 `place_citation` 註記，含 `name` 與 `url`。需 Gemini 2.5 Flash 以上或 3.x。

### 條款：來源標示是硬性要求

Maps ToS 有「No Caching」與「No Creating Content From Google Maps Content」兩條，
但對「用 Maps Grounding Lite 餵給 LLM」開了明文例外 —— **前提是輸出要附上 Maps 來源連結**。
要求是**逐筆**的：

- Display the source name provided in the response
- Link to the source using the `url`
- 來源必須**緊接**在生成內容之後，且使用者**一次互動內看得到**

**單一彙總連結不符合要求。** 當時卡片把來源壓成一行 `🔗 地點 · 1 · 2` 的小字，
是「仍然合規的最短篇幅」——不能再壓，也不能整個移除。

同理，`clients/maps_review.py` **刻意沒有做 TTL 快取**：Maps 條款禁止快取 Places 內容，
而 grounded 輸出能不能快取，文件沒有明確說法。in-flight 去重（同一網址同時被貼兩次）
放在 Cog 層，那不是快取。

---

## 4. 解封條件與探法

### 要等的東西：`reviewSummary`

Places API (New) 的 `reviewSummary` 欄位（已 GA）由 Gemini **跨全部評論**做主題摘要，
正是這功能原本想要的東西：

```jsonc
{
  "text":           { "text": "...", "languageCode": "en" },
  "flagContentUri": "...",
  "disclosureText": { "text": "Summarized with Gemini" },
  "reviewsUri":     "..."
}
```

**2026-08 的支援語言只有英、日、葡、西 —— 臺灣不在清單內，中文完全不支援。**
（更窄的 `generativeSummary` 只支援英文，且僅限印度與美國。）

### 探法

對**臺灣地點**的 Place Details 請求，在 field mask 加上 `reviewSummary`，看欄位有沒有回：

```
GET https://places.googleapis.com/v1/places/<PLACE_ID>?languageCode=zh-TW
X-Goog-Api-Key: <key>
X-Goog-FieldMask: id,displayName,rating,userRatingCount,reviewSummary
```

回得出中文 `reviewSummary` ＝ 可以解封。注意這是 Enterprise + Atmosphere SKU，
探測本身就會計費（月免費額度 1,000 次以內不至於有感）。

### 解封後該怎麼做（設計已想好，不必重新推導）

1. **改動只在兩層**：n8n「maps-review」工作流改打 Places API 取 `reviewSummary`，
   以及 `ui/maps.py` 的版型。契約可以完全不動。
2. `_provenance_line()`（樣本大小提醒）可以整段拿掉 —— 那是為了誠實面對「只有 1 則評論」
   才存在的裝置，跨全部評論的摘要不需要它。
3. `disclosureText`（"Summarized with Gemini"）依規定要顯示。
4. 來源標示的要求不變，`_sources_line()` 的作法可以沿用。

---

## 5. 還原方式

```bash
# 看當時的完整實作
git show archive/maps-review --stat
git checkout archive/maps-review -- tm_bot/ui/maps.py tm_bot/services/maps.py \
    tm_bot/clients/maps_review.py tm_bot/cogs/maps_review.py \
    tests/test_maps.py tests/test_maps_review.py

# 或直接把移除的那個 commit 反轉（wiring 與設定也會一起回來）
git revert <下架 commit>
```

`ui/maps.py` 的模組 docstring 記著每一個版型決定**為什麼**是那樣（含「別再壓了」與原因），
復活時先讀那段，不要重新踩一遍。

### 當時的檔案清單

| 檔案 | 職責 |
| --- | --- |
| `tm_bot/services/maps.py` | 地圖連結辨識（`extract_maps_url`、`is_bare_link`） |
| `tm_bot/clients/maps_review.py` | n8n HTTP 客戶端與契約驗證 |
| `tm_bot/cogs/maps_review.py` | Discord 事件處理與 in-flight 去重 |
| `tm_bot/ui/maps.py` | Embed 版型與錯誤文案 |
| `tests/test_maps.py`、`tests/test_maps_review.py` | 連結辨識、契約、版型 |

一併移除的 wiring 與設定：`bot.py`（`ROUTE_MAPS`、`_is_maps_channel()`、
`COG_MAPS_REVIEW`、客戶端初始化）、`config.py`（`n8n_maps_review_webhook_url`、
`n8n_maps_review_timeout`、`maps_review_channel_id`）、`config/config.ini`、`.env.example`。

### n8n 那端

n8n 的「maps-review」工作流**不在本專案版控範圍內**（由主人的 n8n Agent 維護）。
下架時它同時掛著兩個入口，**兩個都要處理**：

1. `/webhook/maps-review` —— bot 直連的入口。bot 端移除後自然沒人呼叫。
2. **TM AI Agent 的 `maps_review` 工具** —— 這個不會因為 bot 改動而失效。
   使用者在助手頻道問「這家好吃嗎？<地圖連結>」仍會走到它。
   要完整下架，**必須在 n8n 端把這個工具停用或移除**。
