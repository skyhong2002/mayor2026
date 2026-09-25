# 部署

## 正式機直接提供（2026-09 起）

`mayor2026.observe.tw` 的 DNS 是 A 記錄直指新竹機器（sky-mini，140.113.240.11，DNS only）。機器上的 Caddy
（`/usr/local/etc/caddy/Caddyfile`）以 `file_server` 提供 `/Users/skyhong/Documents/mayor2026/published/current`，
404 時回 `/404.html`。`scripts/run_pipeline.py --publish-local`（launchd plist 預設）會呼叫 `scripts/publish_local.py`
把 `site/` 複製到 `published/releases/<ts>-<sha>/` 再原子切換 `current` / `previous` 符號連結，保留最近 5 份。
Caddy 設定變更後：`/usr/local/sbin/caddy reload --config /usr/local/etc/caddy/Caddyfile --adapter caddyfile`。

## （備援）GitHub Pages

## 一次性設定

1. `gh repo create mayor2026 --public --source=. --remote=origin`（或手動在 GitHub 建立 public repo 後
   `git remote add origin git@github.com:<user>/mayor2026.git`）。
2. `git push -u origin main`。
3. pipeline 資料由 `scripts/sync_pipeline_data.py` 自動還原並推送到獨立的 `data` 分支；排程使用的
   GitHub credentials 必須具有該分支的讀寫權限。首次 migration 完成後不需人工切換分支。
4. 在 GitHub repo Settings → Pages，Source 選擇 `Deploy from a branch`，Branch 選 `gh-pages` / `/`（root）。
   `scripts/publish_github_pages.py` 第一次執行時會自動建立 `gh-pages` 分支並在其中放入
   `.github/workflows/deploy.yml`，之後 push 到 `gh-pages` 會自動觸發 Pages 部署。
5. 自訂網域：DNS 已設定 `mayor2026.observe.tw` CNAME 指到 `skyhong2002.github.io`，
   `publish_github_pages.py` 預設就會寫入這個 CNAME（可用 `MAYOR_PAGES_CNAME` 環境變數或
   `--cname` 覆寫；傳空字串則回到預設 `*.github.io` 網址）。GitHub repo Settings → Pages 的
   custom domain 也已設為 `mayor2026.observe.tw`，等憑證簽發後記得勾 Enforce HTTPS。

## 新竹機器排程（launchd）

```bash
cp deploy/tw.observe.mayor2026.pipeline.plist ~/Library/LaunchAgents/
# 編輯 plist，把 /Users/REPLACE_ME/mayor2026 換成實際路徑
launchctl load ~/Library/LaunchAgents/tw.observe.mayor2026.pipeline.plist
```

`StartCalendarInterval` 排在每天 00:00 / 06:00 / 12:00 / 18:00（一天四次）。不用擔心打爆平台：
pipeline 有 lock 防止重疊執行，抓取層也有各自的節流（Instagram 依發文頻率每 12–168 小時抓取、每輪最多 6 個來源、
Facebook Apify 依月預算 pacing、請求之間有延遲），大多數 tick 只會抓增量並重建站台。
來源失敗會退避重試，IG 401／429 會啟動共用冷卻。詳見 [抓取與健康機制](../docs/ingestion-health.md)。
log 寫到 `~/Library/Logs/mayor2026/pipeline.log` 與 `pipeline.err.log`（repo 內的 `logs/` 不再使用）。

## 遠端維運建議

- 用 Tailscale 讓開發機可以隨時 SSH 進新竹的 macOS，不用處理學校網路的固定 IP／防火牆。
- 抓取程式本身也放在這個 git repo；機器每次執行前 `git pull`，遠端改 code 下次排程自動生效。
- 建議加 healthchecks.io 之類的心跳監控：pipeline 跑完 ping 一次，超過預期時間沒 ping 就寄信通知，
  避免機器悄悄掛掉很久才發現。
- 系統偏好設定關閉自動睡眠、開啟停電後自動開機，並用 caffeinate 或類似工具保持機器喚醒。
