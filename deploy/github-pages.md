# 部署到 GitHub Pages

## 一次性設定

1. `gh repo create mayor2026 --public --source=. --remote=origin`（或手動在 GitHub 建立 public repo 後
   `git remote add origin git@github.com:<user>/mayor2026.git`）。
2. `git push -u origin main`。
3. 在 GitHub repo Settings → Pages，Source 選擇 `Deploy from a branch`，Branch 選 `gh-pages` / `/`（root）。
   `scripts/publish_github_pages.py` 第一次執行時會自動建立 `gh-pages` 分支並在其中放入
   `.github/workflows/deploy.yml`，之後 push 到 `gh-pages` 會自動觸發 Pages 部署。
4. 自訂網域：DNS 已設定 `mayor2026.observe.tw` CNAME 指到 `skyhong2002.github.io`，
   `publish_github_pages.py` 預設就會寫入這個 CNAME（可用 `MAYOR_PAGES_CNAME` 環境變數或
   `--cname` 覆寫；傳空字串則回到預設 `*.github.io` 網址）。GitHub repo Settings → Pages 的
   custom domain 也已設為 `mayor2026.observe.tw`，等憑證簽發後記得勾 Enforce HTTPS。

## 新竹機器排程（launchd）

```bash
cp deploy/tw.observe.mayor2026.pipeline.plist ~/Library/LaunchAgents/
# 編輯 plist，把 /Users/REPLACE_ME/mayor2026 換成實際路徑
launchctl load ~/Library/LaunchAgents/tw.observe.mayor2026.pipeline.plist
```

`StartInterval` 每 30 分鐘跑一次（與 Harmonica-in-Taiwan 相同節奏）。不用擔心打爆平台：
pipeline 有 lock 防止重疊執行，抓取層也有各自的節流（Instagram 預設 12 小時抓一次、
請求之間有延遲），大多數 tick 只會抓 Threads/YouTube 增量並重建站台。

## 遠端維運建議

- 用 Tailscale 讓開發機可以隨時 SSH 進新竹的 macOS，不用處理學校網路的固定 IP／防火牆。
- 抓取程式本身也放在這個 git repo；機器每次執行前 `git pull`，遠端改 code 下次排程自動生效。
- 建議加 healthchecks.io 之類的心跳監控：pipeline 跑完 ping 一次，超過預期時間沒 ping 就寄信通知，
  避免機器悄悄掛掉很久才發現。
- 系統偏好設定關閉自動睡眠、開啟停電後自動開機，並用 caffeinate 或類似工具保持機器喚醒。
