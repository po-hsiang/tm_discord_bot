# 開發規格：`game_deals` 工具擴充 Steam 遊戲資料

> **這份文件給誰**：主人的 n8n 開發 Agent。
> **為什麼放在 bot 的 repo**：`game_deals` 工具本身在 n8n 端（不在本專案版控內），
> 但它的輸出直接決定週五推播的內容，屬於跨服務契約 —— 與 HANDOVER 第三節記錄 n8n 工作流
> 的作法一致。**Discord bot 端不需要任何改動。**
> **撰寫日期**：2026-08-20（端點與欄位皆為當日實測結果）

目標：週五 22:00 的「週末遊戲情報」推播中，**Steam 特惠的每一款**都要附上更多介紹資料。

---

## 0. 先講三個不能破壞的既有約定

1. **`GAME_DEALS_UNAVAILABLE` 哨兵字串必須保留**。bot 端靠它判斷「本週靜默跳過」，
   拿掉會讓故障時貼出半成品。**只有「連特惠清單都拿不到」才回哨兵** —— 個別遊戲的
   補充資料抓不到不算故障（見 §4 降級規則）。
2. **每款遊戲一定要附商店連結**。bot 端的提詞要求把遊戲名寫成 `[名稱](<網址>)`，
   並明令「原樣複製工具提供的連結，不可自行改寫或猜測」。工具沒給連結，模型就只會寫名稱。
3. **工具只回資料，不要組文案**。版型、語氣、挑選哪幾款都在 bot 端的提詞裡
   （`tm_bot/services/scheduler/prompts.py`），工具回結構化資料就好。

## 1. 要加的欄位

| 欄位 | 格式 | 來源 |
| --- | --- | --- |
| `discount_ends` | `"2026-08-26 00:00:00"`（**到秒**，Asia/Taipei） | `featuredcategories` → `discount_expiration`（Unix 秒） |
| `release_date` | `"2024-08-19"`（**YYYY-MM-DD**） | `GetItems` → `release.steam_release_date`（Unix 秒） |
| `reviews_all` | `{label, count, percent}` | `GetItems` → `reviews.summary_filtered` |
| `reviews_tchinese` | 同上，**無繁中評論時給 `null`** | `GetItems` → `reviews.summary_language_specific` |
| `players_now` | 整數 | `GetNumberOfCurrentPlayers` → `player_count` |
| `blurb` | 繁中一句話，≤ 80 字，**須做繁體正規化**（見 §5.3） | `appdetails` → `short_description` |

**明確不要**（已排除，不要自行加回來）：購買人數、近期平均在線人數、開發商／發行商、
遊戲類型、是否支援繁中、近 30 天評價、近期尖峰在線、Metacritic 分數。

> - **購買人數官方根本沒有**，市面數字都是用評論數反推的估算（誤差 20~50%），不要接第三方來源。
> - **近 30 天評價**與 `reviews_all` 的統計口徑不同，並排會互相打臉 —— 實測有遊戲近 30 天
>   10,738 篇 > 總數 10,644 篇。
> - **近期尖峰在線**官方沒載明統計區間（CS2 回 119 萬，但其全時紀錄約 180 萬）。

### `blurb` 的用途：給模型素材，不是拿來照抄

bot 端的提詞要模型為每款寫「一句話重點」。開發商與類型都排除後，模型手上**沒有任何關於
這款遊戲的事實素材**，只能靠訓練記憶 —— 對《黑神話》這種名作沒問題，對冷門獨立遊戲就是
幻覺風險（會寫出遊戲根本沒有的玩法）。`blurb` 是 Steam 官方的繁中文案，作為事實依據。

## 2. 呼叫計畫

全部端點**免 API Key**。每款 Steam 遊戲 3 次呼叫，加上清單 1 次；5 款共 16 次，一週一次。
呼叫之間間隔 200ms。實測連打 12 次未觸發限流。

### ① 特惠清單（每次執行 1 次）

```
GET https://store.steampowered.com/api/featuredcategories?cc=tw&l=tchinese
```

取 `specials.items[]`，每筆可用：`id`(appid)、`name`、`discount_percent`、
`original_price`、`final_price`（**單位為分，要 ÷100**）、`currency`(TWD)、
**`discount_expiration`**(Unix 秒)。

> ⚠️ `specials` 只回 **10 筆**，且是輪播子集，不是全站特惠。若覺得候選太少不好挑，
> 可另外取同一份回應的 `top_sellers` 補「知名大作」的覆蓋率（選用）。

商店連結自行組出：`https://store.steampowered.com/app/<appid>`

### ② 商店詳細（每款 1 次）

```
GET https://store.steampowered.com/api/appdetails?appids=<appid>&cc=tw&l=tchinese
```

取 `<appid>.data.short_description` → `blurb`（正規化後）。

### ③ 評價與發行日（每款 1 次）

```
GET https://api.steampowered.com/IStoreBrowseService/GetItems/v1/?input_json=<URL-encoded JSON>
```

```jsonc
{
  "ids": [{ "appid": 2358720 }],
  "context": { "language": "tchinese", "country_code": "TW", "steam_realm": 1 },
  "data_request": { "include_reviews": true, "include_release": true }
}
```

回應 `response.store_items[0]`：

```jsonc
{
  "release": { "steam_release_date": 1724025600 },
  "reviews": {
    "summary_filtered":          { "review_count": 877115, "percent_positive": 96,
                                   "review_score": 9, "review_score_label": "壓倒性好評" },
    "summary_language_specific": { "review_count": 9564,   "percent_positive": 93,
                                   "review_score": 9, "review_score_label": "極度好評" }
  }
}
```

`summary_filtered` 的數字**與商店頁顯示一致**，直接用，不要改用 `appreviews` 端點另算
（那個的 `purchase_type` 預設值不同，算出來會對不上使用者看到的數字）。

### ④ 此刻遊玩人數（每款 1 次）

```
GET https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=<appid>
```

取 `response.player_count`。`response.result != 1` 時視為取不到。

## 3. 回傳格式

Steam 與 Epic **兩段分開**，Epic 維持原樣（Epic 沒有這些資料，不要嘗試補）。

```jsonc
{
  "ok": true,
  "epic_free": [
    { "name": "Caravan SandWitch",
      "url": "https://store.epicgames.com/zh-TW/p/caravan-sandwitch-05ff58",
      "claim_ends": "2026-08-20 23:00:00" }
  ],
  "steam_specials": [
    {
      "name": "黑神話：悟空",
      "appid": 2358720,
      "url": "https://store.steampowered.com/app/2358720",
      "discount_percent": 30,
      "price_original": 1280,
      "price_final": 896,
      "currency": "TWD",
      "discount_ends": "2026-08-26 00:00:00",
      "release_date": "2024-08-19",
      "reviews_all":      { "label": "壓倒性好評", "count": 877115, "percent": 96 },
      "reviews_tchinese": { "label": "極度好評",   "count": 9564,   "percent": 93 },
      "players_now": 13973,
      "blurb": "以中國神話為背景的動作角色扮演遊戲，扮演天命人踏上西遊之路。"
    }
  ]
}
```

雙來源皆故障時維持原本行為：回 `GAME_DEALS_UNAVAILABLE`。

## 4. 降級規則（重要）

**每一個補充欄位都要能單獨失敗。** ①`featuredcategories` 是唯一的必要來源，
其餘任何一個掛掉，只是那個欄位變 `null`，不影響其他遊戲、也不影響整則推播。

| 情況 | 該怎麼做 |
| --- | --- |
| `featuredcategories` 取不到 | 才回 `GAME_DEALS_UNAVAILABLE` |
| 某款的 `GetItems` 失敗 | 該款 `reviews_all`／`reviews_tchinese`／`release_date` 給 `null` |
| 某款的 `appdetails` 失敗 | `blurb` 給 `null` |
| 某款的線上人數失敗 | `players_now` 給 `null` |
| **沒有繁中評論**（實測有此案例） | `reviews_tchinese` 給 **`null`**，不要給 `{count: 0}` |
| `discount_expiration` 欄位不存在 | `discount_ends` 給 `null`，**不要自己推算或編一個日期** |
| `original_price` 為 0 或缺失 | 該款只報折扣百分比，價格欄位給 `null` |

`null` 的欄位在提詞端就是「這行不提這件事」，不要回空字串或 `0`，也不要回「無資料」這種
會被模型照抄進文案的字串。

## 5. 三個實測踩到的坑

1. **`original_price` / `final_price` 單位是「分」**。`128000` 是 NT$1,280，不是 12.8 萬。
   另外 `appdetails` 的 `price_overview.initial_formatted` **沒打折時是空字串**，
   不能直接當原價用 —— 這次規格不取它，就別繞回去用。
2. **`discount_expiration` 是 UTC Unix 秒**。要用 `Asia/Taipei` 轉，否則會少 8 小時，
   「特惠倒數」直接錯一天。格式化到秒：`YYYY-MM-DD HH:MM:SS`。
3. **`l=tchinese` 的回傳會夾簡體字形**。實測《黑神話：悟空》的 `short_description`
   出現「在**游**戲中」「**爲**了探尋」與中文彎引號 `“ ”` —— 那是簡轉繁沒做完。
   `blurb` **回傳前務必做臺灣繁體用字正規化**（至少處理 游→遊、爲→為、彎引號→「」）。
   **這件事很重要**：好虎粉一眼就看得出簡體字。

## 6. 驗收方式

請對以下三款各跑一次，把工具的原始回傳貼給主人看：

| 遊戲 | appid | 要驗什麼 |
| --- | --- | --- |
| 黑神話：悟空 | 2358720 | 全部與繁中的**標籤不同**（壓倒性好評 877,115 篇 vs 極度好評 9,564 篇），兩者不可混用；`blurb` 的簡體字是否已正規化 |
| 鐵巢重砲 | 2950790 | **無繁中評論** → `reviews_tchinese` 必須是 `null`，不是 `{count: 0}` |
| Kingdom Come: Deliverance II | 1771300 | 一般案例；順便確認 Metacritic（89 分）**沒有**被塞進回傳 |

另外請確認：**故意讓 `GetItems` 失敗**時，該款其他欄位仍完整、其他遊戲不受影響、
整則推播照常產出。
