# 2026mayor - 六都市長候選人貼文監測站

一個獨立、以公開資料為主的六都（臺北、新北、桃園、臺中、臺南、高雄）市長候選人官方發文監測站。定期從候選人公開的
Facebook、Instagram、Threads、YouTube、官網等來源抓取貼文，正規化、分類議題比例，輸出成靜態網站、JSON API 與 RSS。

## 目前輸出（規劃中，尚未部署）

- 網站首頁：六都候選人總覽矩陣
- `/<city>/<candidate>/`：單一候選人跨平台合併時間軸 + 議題比例圖表
- `/api/*.json`：公開 JSON API
- `/feeds/<candidate>.xml`：每位候選人一條 RSS

## 專案結構

```text
.
├── data/
│   ├── sources/
│   │   └── candidate-watchlist.csv   # 人工維護：候選人 x 平台公開連結
│   └── feeds/
│       ├── social_sources.json       # 由 CSV 轉出的抓取設定（可重建，不進 git）
│       ├── social_feed_inbox.jsonl   # 抓取正規化後的全量貼文（進 git，保留歷史）
│       └── social_candidates.jsonl   # 分類後的貼文（進 git）
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

- `data/sources/candidate-watchlist.csv` 是唯一的人工維護清單：每位候選人一列，含城市、政黨、與各平台公開連結。
  `public_id` 是穩定 ID，不因排序或插入列重編。
- `scripts/build_social_sources.py` 把 CSV 轉成抓取設定 `data/feeds/social_sources.json`。
- 抓取層目前是骨架（見下方「目前完成度」），之後會透過 RSSHub（FB/IG/Threads）、Apify（Facebook 備援）、
  yt-dlp（YouTube）與官網 scraper 取得貼文，寫入 `data/feeds/social_feed_inbox.jsonl`。
- `scripts/classify_topics.py` 用關鍵字規則為每則貼文標記議題（交通、住宅、社福、環境、教育、經濟、治安⋯），
  寫入 `data/feeds/social_candidates.jsonl`。
- `scripts/build_public_data.py`、`scripts/build_spectrum.py` 純讀檔計算每位候選人的議題比例與光譜位置，
  供建站使用。

`data/feeds/*.jsonl` 刻意追蹤進 git（跟大多數爬蟲專案的慣例相反）：候選人刪除貼文本身就是需要留存的紀錄。

## 目前完成度

這是初始骨架版本：

- [x] CSV → JSON 來源設定轉換
- [x] 抓取 adapter 骨架（RSSHub / Apify Facebook / YouTube yt-dlp / 官網 scraper），可用假資料或公開 demo
      RSSHub 實例測試；正式運作需要在執行環境設定 `MAYOR_RSSHUB_BASE`、`APIFY_TOKEN` 等環境變數
- [x] 正規化、去重、議題分類
- [x] 靜態站建置、驗證、gh-pages 發布腳本
- [ ] 真實候選人名單（`candidate-watchlist.csv` 目前只有佔位/TODO 列）
- [ ] 官網逐一 adapter（依真實候選人網站結構撰寫）
- [ ] 排程機器（新竹 macOS + RSSHub）的實際串接與 Tailscale 遠端維運

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
最後執行 `validate_public_outputs.py`；驗證失敗不會發佈。

## 資料回報

新增候選人、修正資料請透過 GitHub Issue：`.github/ISSUE_TEMPLATE/add-candidate.yml`、`correct-data.yml`。
回報內容會公開顯示，請只填公開可查資料。

## License

MIT. See `LICENSE`.
