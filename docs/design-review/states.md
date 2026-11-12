# 設計評審截圖清單

每一輪都照這份清單截圖，ID 與 `tools/states.mjs` 一致。每個狀態截兩張：

| 尺寸 | 視窗 | 像素比 | 截圖高度 |
|---|---|---|---|
| `desktop` | 2560 × 1440（1440p） | 1 | 從頁首或指定錨點起，最多 2160 px |
| `mobile` | 390 × 844（觸控） | 2 | 從頁首或指定錨點起，最多 1688 CSS px |

固定條件：

- **資料**：本機 `data` 分支 `65967f50f1a3`（2026-11-10T22:02:07Z，領先 origin 1 個 commit）的三個 pipeline 檔，以 `build_public_data` → `build_spectrum` → `build_qualitative` → `generate_rss_feeds` 產生 `site/api`、`site/feeds`（時鐘固定在快照時間）。`status.json` 用正式站同一時間點（generatedAt 2026-11-11 06:02 GMT+8）的公開檔。圖片與頭像依 `fetch_media_cache` 的檔名規則（URL 雜湊）從正式站公開路徑唯讀下載一次。凍結在 `/tmp/mayor-review/fixture`（檔案清單 SHA-256 `463c7d02…47eae1`）。
- **空資料**：同一程式碼、候選人與來源設定不變、貼文為 0 的建置（`/tmp/mayor-review/fixture-empty`），代表開票季前或資料重建中的情況。
- **時鐘**：伺服器端渲染固定在 2026-11-10T22:30Z；瀏覽器固定在 2026-11-11 06:30（Asia/Taipei）。`Math.random` 以固定種子取代，讓「中立隨機排序」每輪相同。
- **字型**：Noto Sans TC（使用者字型目錄，未改系統設定）。減少動態效果。
- 載入中／錯誤以 Playwright 攔截前端 JSON：`hang` 不回應、`error` 回 500。

## 頁面與狀態

| ID | 頁面 | 狀態 | 重現方式 |
|---|---|---|---|
| `home` | 最新 `/` | 有資料 | — |
| `home-dark` | 最新 | 深色 | `prefers-color-scheme: dark` |
| `home-city` | 最新 | 只看臺中 | `?city=taichung` |
| `home-filter-open` | 最新 | 第一個欄位篩選面板展開 | 點可見的 `.col-btn[data-act=filter]`，只截視窗 |
| `home-no-results` | 最新 | 關鍵字無結果 | `?q=zzqxv` |
| `home-loading` | 最新 | 篩選後等待貼文包 | `?city=taipei&topic=housing`，`/data/feed/**` 不回應 |
| `home-error` | 最新 | 篩選後貼文包錯誤 | 同上，回 500 |
| `home-empty` | 最新 | 空資料 | 空資料建置 |
| `menu-open` | 全站導覽 | 「更多」選單展開 | 點 `.nav-more > summary`，只截視窗 |
| `cand` | 候選人 `/taipei/shen-poyang/` | 貼文多 | — |
| `cand-dark` | 候選人（同上） | 深色 | — |
| `cand-sparse` | 候選人 `/kaohsiung/chang-ching/` | 貼文少（88 則） | — |
| `cand-filter` | 候選人 | 議題「住宅」＋ Instagram | `?topic=housing&platform=instagram`，錨點時間軸 |
| `cand-no-results` | 候選人 | 篩選無結果 | `?q=zzqxv`，錨點時間軸 |
| `cand-loading` | 候選人 | 篩選等待分頁資料 | `?q=捷運`，`/data/candidate/**` 不回應 |
| `cand-error` | 候選人 | 篩選分頁資料錯誤 | 同上，回 500 |
| `cand-empty` | 候選人 | 空資料 | 空資料建置 |
| `sources` | 目錄 `/source/` | 全部 | — |
| `sources-filter` | 目錄 | 高雄 | `?city=kaohsiung` |
| `sources-no-results` | 目錄 | 搜尋無結果 | `?q=zzqxv` |
| `source-detail` | 帳號明細 `/source/shen-poyang/` | 帳號多 | — |
| `source-detail-sparse` | 帳號明細 `/source/chang-ching/` | 帳號少 | — |
| `spectrum` | 議題光譜 `/spectrum/` | 有資料 | — |
| `spectrum-dark` | 議題光譜 | 深色 | — |
| `spectrum-empty` | 議題光譜 | 空資料 | 空資料建置 |
| `topic` | 議題 `/spectrum/housing/` | 有資料 | — |
| `topic-empty` | 議題 | 空資料 | 空資料建置 |
| `policy` | 議題選擇器 `/policy-match/` | 第一題 | — |
| `policy-results` | 議題選擇器 | 選了交通、住宅、托育 | `#c=daily-transport,daily-housing,care-child` |
| `policy-results-dark` | 議題選擇器 | 結果、深色 | 同上 |
| `policy-loading` | 議題選擇器 | 結果等待證據貼文 | `/api/policy-match.json` 不回應 |
| `policy-error` | 議題選擇器 | 證據貼文錯誤 | 同上，回 500 |
| `policy-empty` | 議題選擇器 | 空資料的結果 | 空資料建置 |
| `search` | 搜尋 `/search/` | 尚未輸入 | — |
| `search-results` | 搜尋 | 「捷運」 | `?q=捷運` |
| `search-filter` | 搜尋 | 「捷運」＋臺中＋Facebook | `&city=taichung&platform=facebook` |
| `search-no-results` | 搜尋 | 無結果 | `?q=zzqxv` |
| `search-loading` | 搜尋 | 索引載入中 | `/data/search-index.json` 不回應 |
| `search-error` | 搜尋 | 索引錯誤 | 同上，回 500 |
| `search-empty` | 搜尋 | 空資料 | 空資料建置，`?q=捷運` |
| `feeds` | 訂閱 `/feeds/` | — | — |
| `status` | 資料狀態 `/status/` | — | — |
| `status-dark` | 資料狀態 | 深色 | — |
| `status-filter` | 資料狀態 | 只看 Instagram | `?platform=instagram` |
| `status-empty` | 資料狀態 | 空資料 | 空資料建置（status 由該建置產生） |
| `about` | 關於 `/about/` | — | — |
| `not-found` | `/no-such-page/` | 404 | — |

## 參考對手

第一輪截一次，之後每輪重用同一組檔案（`/tmp/mayor-review/sets/reference`）：

| ID | 網址 | 對應的我方頁面 |
|---|---|---|
| `readr-home` | https://www.readr.tw/ | 中文資料新聞首頁 |
| `readr-election` | https://www.readr.tw/category/election | 選舉專題列表 |
| `groundnews-home` | https://ground.news/ | 跨來源比較、立場分布 |
| `groundnews-interest` | https://ground.news/interest/taiwan | 主題頁 |
| `bluesky-profile` | https://bsky.app/profile/bsky.app | 候選人時間軸 |
| `bluesky-search` | https://bsky.app/search?q=taipei | 搜尋 |

## 重現

```bash
R=/tmp/mayor-review T=docs/design-review/tools
# 1. 建置（基準版用 `git archive main` 匯出的目錄）
python3 $T/build_snapshot.py SRC $R/build/NAME
python3 $T/build_snapshot.py SRC $R/build/NAME-empty --fixture $R/fixture-empty
# 2. 唯讀預覽
python3 $T/serve.py $R/build/NAME/site --port 8420 &
python3 $T/serve.py $R/build/NAME-empty/site --port 8421 &
# 3. 截圖（$T/node_modules 連到裝有 playwright 的目錄）
node $T/capture.mjs site http://127.0.0.1:8420 http://127.0.0.1:8421 $R/sets/NAME
node $T/capture.mjs references $R/sets/reference      # 只在第一輪
# 4. 組一輪盲測
python3 $T/make_round.py N $R/sets/NAME
```

`tools/shot.mjs`（取代只能在 macOS 跑的 `tools/shot.sh`）可截單頁：`node tools/shot.mjs /spectrum/ out.png 1440 2000 dark`。
