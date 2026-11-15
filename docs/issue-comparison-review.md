# 臺北市全議題比較 Review

此試跑與正式排程、正式站資料分開。官方名單保留臺北市 6 位市長候選人；所有既有 15 類議題都列出，另補「城市治理與空間」以容納行政改革、公共空間等政策，並從完整文本抽取政策問題。政策原頁另保留所有層級的小標與完整收錄文本，不以固定熱門題清單取代。

## 重建

```bash
# 準備來源（官網政策專頁與既有公開 API；不啟動正式 pipeline）
python3 scripts/build_issue_comparisons.py --prepare

# 使用本專案已存在的 AI gateway 憑證；不把憑證寫入 review 網站
python3 scripts/build_issue_comparisons.py --analyze --repair --briefs --env-file /srv/mayor2026/.env

# 純離線渲染，先檢查名單、議題、引用及檢核狀態
python3 scripts/build_issue_comparisons.py --render
```

初次執行可先將正式主機 ingestion inbox 中的臺北市列以唯讀方式複製到
`private/comparison-taipei/inputs/inbox-taipei.json`。這能納入尚未完成舊分類的貼文；沒有此檔時仍可使用公開 API，但必須依該 API 的實際收錄範圍說明。

`private/comparison-taipei/` 不進 git：

- `manifest.json`：候選人、來源版本、去重關係、政策標題與擷取範圍。
- `cache/`：內容定址的每次 Sky-Quality 結果、實際模型與 token usage；不包含認證資訊。
- `claims.json`：逐條主張與抽取引用驗證紀錄。
- `topics/`：跨候選人對齊後的議題問題、比較與語意檢核。
- `comparison.json`：完整私有診斷快照，包含未通過的比較草稿。
- `review-site/`：可供 review 的靜態網站，**只提供此目錄**。不通過的摘要在 HTML、搜尋欄位及公開 JSON 中都以狀態訊息取代。

新增的分析、對齊、比較與語意驗證一律請求 `sky-quality`，沒有其他模型備援。中斷後重新執行會讀取已完成的內容快取；不需要重付所有分析請求。

`--briefs` 另以完整議題的主張整理整體做法差異，再獨立檢核引用。它讓讀者先理解不同政策工具，再深入所有細小問題；不以缺資料推定反對，也不以主張數量評定優劣。

`--repair` 對語意檢核指出問題的摘要依原文與意見修正一次，再重新檢核；仍不通過的文字不對外顯示，原文繼續保留。

## Review 網路服務

使用獨立且未占用的 Tailscale HTTPS port，保留主機既有 Serve 設定。例如本次使用 `12449`：

```bash
tailscale serve --bg --https=12449 --yes /home/sky/Projects/mayor2026/private/comparison-taipei/review-site
```

網址路徑為 `/compare/taipei/`。這是 tailnet 內的 review 版本，未發布到正式網域，也不使用 Funnel。

關閉本次入口時只關閉該 port，**不要 reset 主機所有 Serve 設定**：

```bash
tailscale serve --https=12449 off
```

## 驗證

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --check site/assets/pages/comparison.js
git diff --check
```

專屬測試涵蓋缺少候選人／議題、錯誤引用、錯誤歸屬、單人被誤寫成分歧、主張遺漏、長文分段、完整原頁小標，以及檢核未通過時隱藏結論但保留原文。

## 比較表介面

主畫面使用固定候選人欄首、固定政策問題列首的橫向比較表。議題使用原生下拉選單，比較對象使用可勾選的選單，不使用 tab。預設並排已有來源的 3 位候選人，其餘候選人可從同一選單加入；全部 6 位仍完整保留。所有 999 個問題直接呈現摘要，來源原文可在儲存格內展開；手機也維持表格，左右捲動比較。

候選人依收錄的去重貼文數由多到少排列，同數時依官方號次，政策專頁不計入貼文數。手機版把政策題目放在該列上方，畫面內可並排前兩位；表格使用 layout／paint containment，避免內部捲動影響整頁。頭貼在 `--prepare` 從既有候選人 API 的圖片網址快取至 `inputs/avatars/`，離線渲染時複製到 review 靜態資產。

表格省略跨候選人的判讀旁白與重複提醒，並從已通過檢核的候選人摘要中刪除「需核對」「不能直接視為」等編輯說明。政策本身的數字、資格、研議狀態與申請條件保留；直接引文與私有分析快照不改寫。

頁面會明示每位候選人的資料覆蓋。尚無來源者仍有完整欄位，不能被當成反對方；本人貼文也不能取代尚未取得的正式公報政見。

## 正式網站

正式路徑為 `/compare/taipei/`，導覽入口為「政見比較」。`generate_site_pages.py` 每次都會從 `data/comparisons/taipei.json.gz` 載入已 review 的公開快照，檢查完整性後離線產生頁面及 `/api/comparison.json`。靜態頭貼隨 `site/assets/comparison-avatars/` 一同版本控制。此階段不重新呼叫模型，也不改寫原始貼文；分析截止時間保持為快照本身的時間。

正式 renderer 保留首頁、robots.txt 與本機站內導覽，並移除 review 標記及 noindex。頁面納入 sitemap，發布前驗證涵蓋比較資料、全部政策問題及頭貼。

正式容器會覆蓋 `/app/data`，需與 elections、sources 一樣加入唯讀來源掛載：

```yaml
- /home/sky/Projects/mayor2026/data/comparisons:/app/data/comparisons:ro
```

可使用 `python3 scripts/generate_site_pages.py --site-dir <stage>`，從既有公開快照進行隔離建置，再通過來源覆蓋及公開輸出驗證，最後沿用 `scripts/publish_local.py --site <stage> --publish-root /srv/mayor2026/published` 原子切換 release。來源資料更新需先重新分析及 review，再替換版本控制中的壓縮快照；私人診斷與 AI 快取不得直接發布。
