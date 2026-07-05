# mayor2026 - Workspace Rules

## 新增或修改監看帳號（`data/sources/watchlist_accounts.csv`）

1. **穩定 ID**：`account_id` 是抓取狀態、頭貼快取、貼文 `source_id` 的 join key；`candidate_id`
   決定候選人頁 URL（`/<city>/<candidate_id>/`、`/source/<candidate_id>/`）。不要因排序或插入列重編。
2. **信心欄位必填**：每列都要有 `account_role`（campaign/personal/incumbent/party/affiliated）與
   `verification`（first_party/cross_ref/unverified），佐證寫進 `evidence` 欄。查證過程記錄在
   `data/sources/candidate-accounts-research-*.md`。
3. **停用而非刪除**：帳號失效時把 `active` 設為 false，保留該列作為歷史紀錄。

## RSSHub 路由（rss.observe.tw）

- Instagram 一律用 V2 web-API 路由 `/instagram/2/user/:key`（實例只配置 IG_COOKIE；V1 私有 API
  路由需要帳密、基於帳號安全刻意停用）。
- Threads 是 `/threads/:user`，不是 `/threads/user/:user`。
- 抓取失敗時先看 `state/social_fetch_state.json` 的 `last_error` 或 `/status/` 頁——
  rsshub_fetcher 會解析 RSSHub 錯誤頁裡的真正錯誤訊息（如 ConfigNotFoundError），不要只看 503。

## 建置與驗證

1. 本機 dry run：`python3 scripts/run_pipeline.py --skip-watch --no-lock`。
2. 驗證：pipeline 會自動跑 `check_source_coverage.py` 與 `validate_public_outputs.py`；
   驗證失敗不得發佈。
3. 執行狀態看 `site/api/pipeline-runtime.json` 或 `/status/` 頁。

## 部署

- 原始檔（`data/`、`scripts/`、`site/assets`、`site/templates`）commit 到 `main`。
- 生成輸出（`site/api`、`site/feeds`、`site/status`、各候選人頁、sitemap 等）只進 `gh-pages`，
  由 `scripts/publish_github_pages.py` 發布；不要 commit 回 `main`。

## 資料保存原則

`data/feeds/social_feed_inbox.jsonl` 與 `social_candidates.jsonl` 刻意追蹤進 git——候選人刪文
本身就是需要留存的紀錄。只能 append，不要改寫歷史列。
