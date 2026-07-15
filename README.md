# 2026 市長官方來源觀測站

`mayor2026.observe.tw` 是一個獨立、以公開資料為主的六都（臺北、新北、桃園、臺中、臺南、高雄）市長候選人官方發文觀測站。定期從候選人公開的
Facebook、Instagram、Threads、YouTube、官網等來源抓取貼文，正規化、分類議題比例，輸出成靜態網站、JSON API 與 RSS。

## 目前輸出

- 網站首頁：<https://mayor2026.observe.tw/>（六都候選人總覽 + 最新公開發文河道）
- `/<city>/<candidate>/`：單一候選人跨平台合併時間軸 + 議題比例圖表
- `/source/`：公開來源列表；`/source/<candidate>/`：帳號清單（含性質與驗證等級）
- `/status/`：資料管線狀態（收錄統計、最近一次執行、近期抓取錯誤）
- `/policy-match/`：匿名選擇市政優先議題，對照候選人自主政策倡議貼文
- `/api/*.json`：公開 JSON API（candidates / sources / latest / spectrum / status / posts/<id>）
- `/feeds/`：RSS 訂閱入口；每位候選人一條 `<id>.xml` 與對應 `<id>.json`

## 專案結構

```text
.
├── data/
│   ├── sources/
│   │   ├── candidates.csv            # 人工維護：候選人基本資料（姓名、城市、政黨）
│   │   ├── watchlist_accounts.csv    # 人工維護：候選人 x 平台公開帳號清單（含驗證等級）
│   │   └── candidate-accounts-research-*.md  # 帳號查證來源紀錄，供之後複查
│   └── feeds/
│       ├── social_sources.json       # 由 CSV 轉出的抓取設定（可重建，不進 git）
│       ├── social_feed_inbox.jsonl   # 抓取正規化後的全量貼文（由 data 分支保存）
│       ├── social_candidates.jsonl   # 分類後的貼文（由 data 分支保存）
│       └── source_profiles.json      # 來源頭像快取（由 data 分支保存）
├── scripts/                          # 抓取、正規化、分類、建站腳本
├── site/
│   ├── assets/                       # CSS/JS，source assets，留在 main
│   ├── templates/                    # HTML 模板，留在 main
│   ├── api/、data/、feeds/、city/     # 產生輸出，不進 main，由 gh-pages 分支保存
├── deploy/                           # launchd 排程設定與部署文件
├── .github/ISSUE_TEMPLATE/           # 公開資料回報表單
└── README.md
```

## 資料怎麼蒐集

- `data/sources/candidates.csv` 是候選人基本資料（`candidate_id`、姓名、城市、政黨）；`candidate_id` 是穩定 ID，
  決定候選人頁網址與所有下游資料的 join key，不因排序或插入列重編。
- `data/sources/watchlist_accounts.csv` 是候選人 × 平台的公開帳號清單，每個帳號一列，含 `account_role`
  （campaign/personal/incumbent/party）與 `verification`（first_party/cross_ref/unverified）兩個信心欄位。
  一位候選人在同平台可以有多個帳號（例如競選粉專 + 個人粉專），抓取層會全部監看；建站時的候選人頁連結只挑
  信心最高的一個顯示。這份清單目前的內容來自 2026-07-05 的公開來源查證（見同目錄下的查證紀錄 md 檔）。
- `scripts/build_social_sources.py` 把兩份 CSV 轉成抓取設定 `data/feeds/social_sources.json`。
- 抓取層目前是骨架（見下方「目前完成度」）：Instagram/Threads 走 RSSHub（預設 `https://rss.observe.tw`），
  Facebook 走 Apify（這個 RSSHub 實例沒有註冊 `/facebook/*` route，經 curl 驗證過），YouTube 用 yt-dlp，
  官網則是逐候選人 adapter。全部寫入 `data/feeds/social_feed_inbox.jsonl`。
- `scripts/classify_context.py` 以 OpenAI Responses API 結構化輸出同時判斷議題與主要貼文性質（政策、立場、行政進度、
  資訊公告、澄清、批評、動員、活動、個人、其他）。每篇保留 AI 判斷信心、理由、模型與規範版本；沒有人工審核佇列。
  預設使用 `gpt-5.4-mini`，從 `OPENAI_API_KEY` 或權限為 `600` 的 `~/.config/mayor2026/openai-api-key` 讀取憑證，
  並可用 `MAYOR_AI_MODEL` 覆寫。分類以文字、模型及規範版本雜湊快取，
  因此排程只會處理新貼文或需要重分的貼文。
- `scripts/build_qualitative.py` 產生貼文性質統計及議題選擇器使用的候選人政策議程向量；只有 AI 判為
  「政策／政見」且 `agendaRelevance >= 0.6` 的結果會進入政策配對。
- `scripts/build_public_data.py`、`scripts/build_spectrum.py` 純讀檔計算每位候選人的議題比例與光譜位置，
  供建站使用。

候選人刪除貼文本身也是需要留存的紀錄，因此 pipeline 會把上述三個自動產生檔案提交到獨立的
`data` 分支；`main` 只保留程式碼與人工維護來源，`gh-pages` 則只保存公開網站快照。

## 目前完成度

這是初始骨架版本：

- [x] CSV → JSON 來源設定轉換
- [x] 真實候選人名單（六都 14 位候選人，含多平台帳號與驗證等級）
- [x] 抓取 adapter 骨架（RSSHub Instagram/Threads、Apify Facebook、YouTube yt-dlp、官網 scraper）；
      Instagram/Threads 已對 `rss.observe.tw` 驗證過路由會匹配（但可能因該平台流量限制回傳 503，
      屬預期中的不穩定）；正式運作需要設定 `APIFY_TOKEN` 環境變數
- [x] 正規化、去重、AI 議題與貼文性質分類
- [x] 候選人頁議題／貼文性質篩選
- [x] 議題選擇器（以自主政策倡議貼文為依據，附來源與資料不足提示）
- [x] 靜態站建置、驗證、gh-pages 發布腳本
- [ ] 官網逐一 adapter（依真實候選人網站結構撰寫，見 `scripts/official_site_adapters/`）
- [ ] 排程機器（新竹 macOS）的實際串接與 Tailscale 遠端維運
- [ ] LINE OA、LINE OpenChat、Podcast、TikTok、X 帳號目前只顯示在候選人頁連結，尚未接入抓取

## 建置與發佈

```bash
python3 scripts/run_pipeline.py --skip-watch   # 本機 dry run：只用現有 jsonl 建站，不抓新資料
python3 scripts/validate_public_outputs.py     # 驗證 generated JSON 是否可解析、必要檔案是否存在
python3 scripts/publish_github_pages.py --no-push  # 檢查 gh-pages worktree 複製邏輯
```

正式抓取 + 發布：

```bash
python3 scripts/run_pipeline.py --publish-pages
```

`run_pipeline.py` 會依序重建來源設定、抓取各平台更新、分類議題、建置 `site/api`、`site/data`、`site/feeds`，
最後執行 `validate_public_outputs.py`；驗證成功後才更新 `data` 分支，驗證失敗不會發佈資料或網站。
一般執行會先從 `origin/data` 還原上次資料，避免排程機器的本機狀態成為唯一副本。開發時若要保留
現有本機資料，可加 `--skip-data-restore`；只測試、不推送資料則加 `--data-no-push`。

## 資料回報

新增候選人、修正資料請透過 GitHub Issue：`.github/ISSUE_TEMPLATE/add-candidate.yml`、`correct-data.yml`。
回報內容會公開顯示，請只填公開可查資料。

## License

MIT. See `LICENSE`.
