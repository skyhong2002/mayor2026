# mayor2026.observe.tw — 2026-09 全站重製設計契約

本文件是「觀測站家族」（chumei.observe.tw、harmonica.observe.tw）風格全站重製的**唯一契約**。
所有實作 agent 必須遵守這裡的 URL、檔案歸屬、class 名稱與元件行為；有衝突以本文件為準。
參考素材：`/tmp/ref/chumei_site.css`、`/tmp/ref/chumei_tokens.css`、`/tmp/ref/chumei_observe_tw_.html`、
`/tmp/ref/*.png`（截圖）、`/tmp/ref/ARCH.md`（現有資料契約）。

## 0. 產品定位（不變）

獨立、以公開資料為主的六都市長候選人**官方公開發文**觀測站。非官方、不做民調、不推定立場。
候選人 13 位、六都、五個平台（facebook / instagram / threads / youtube / x）＋官網、Podcast。
所有貼文皆連回原文；本站只索引與分類（議題、發文動機：主動發文 / 回應他方觀點）。

## 1. 視覺語言

- **App 殼（Threads 式）**：桌機固定左側欄 260px；平板（700–1079px）窄欄 76px 只顯示 icon；
  手機頂欄 54px（品牌置中、左上篩選/搜尋鈕）＋底部 tab bar。照抄 chumei 的 breakpoints 與作法。
- **深淺色**：以 `tokens.css` 定義語意色；預設跟隨系統，`<html data-theme="dark|light">` 可覆寫，
  `localStorage.theme` 記憶；`<head>` 內 inline script 先套用避免閃爍。深色為主要展示情境（截圖驗收以深色為主，但淺色必須同樣完整可用）。
- **字型**：`"Noto Sans TC", "PingFang TC", system-ui, -apple-system, "Segoe UI", sans-serif`。不載入 webfont。
- **政治中立配色（重要）**：品牌 accent 使用紫羅蘭系，**不得**用綠（民進黨）、藍（國民黨）、青綠（民眾黨）、黃（時代力量）作為品牌或動作色。
  政黨色只出現在「小面積識別」：頭像外環（story ring / avatar ring）與政黨 chip 前的 6px 圓點。
  - 民進黨 `#1B9431`、國民黨 `#000095`（深色底用 `#5B6CFF`）、民眾黨 `#28C8C8`、司法改革黨 `#8A5A00`（深色 `#E0A83A`）、無黨籍 / 其他 `var(--color-text-muted)`。
  - 六都各有一個中性辨識色（用於欄位標題圓點與 city chip），與政黨無關：
    臺北 `#8B7CF6`、新北 `#F28E6B`、桃園 `#4FB6C9`、臺中 `#E0A83A`、臺南 `#D46A9A`、高雄 `#6BB56B`（淺色底請用同色系加深版，由 tokens 定義 `--city-<slug>` / `--city-<slug>-surface`）。
- **圖表**：spectrum 熱圖與議題比例條使用 accent 單色序列（淺→深），不要彩虹配色。實作前請執行 `dataviz` skill 的規範（Claude agent 可 `Skill(dataviz)`）。
- 圓角、間距、陰影、motion 全部用 tokens；禁止 magic number 顏色。

## 2. 品牌

- 名稱：`2026 市長官方來源觀測站`（`<title>`、footer、meta 使用全名）。
- 側欄字標：`<a class="brand" href="/"><span class="brand-num">2026</span><span class="brand-sub">市長觀測站</span></a>`，
  `brand-num` 用 accent 漸層文字（模仿 chumei 的「竹梅」漸層），`brand-sub` 為 muted 中量字。
- Favicon / logo：沿用 `site/assets/favicon.svg`、`site/assets/logo.svg`。

## 3. URL 地圖（全部保留既有路徑；新增三個）

| 路徑 | 頁面 | 負責 agent |
|---|---|---|
| `/` | 最新：story strip ＋ 六都多欄河道（feed deck） | home |
| `/<city>/<candidate_id>/` | 候選人頁：檔案頭、帳號、議題比例、動機、單欄時間軸 | candidate |
| `/source/` | 候選人與公開來源目錄（harmonica Directory 表格風格） | directory |
| `/source/<candidate_id>/` | 單一候選人監看帳號明細（含 verification、抓取健康） | candidate |
| `/spectrum/` | 議題光譜熱圖 | spectrum |
| `/spectrum/<topic_slug>/` | 單一議題跨候選人比較 ＋ 該議題貼文河道 | spectrum |
| `/policy-match/` | 議題選擇器（先選政策後看候選人） | policy |
| `/status/` | 資料來源狀態（chumei 狀態頁 ＋ harmonica 系統狀態的綜合） | status |
| `/feeds/` | 訂閱入口：每位候選人 RSS/JSON、全站 RSS、API 說明 | directory |
| `/about/` **新** | 關於本站：方法、資料原則（刪文保存）、分類說明、免責、回報連結、GitHub | directory |
| `/search/` **新** | 全站搜尋（純前端，讀 `data/search-index.json`） | home |
| `/404.html` **新** | GitHub Pages 404 | directory |
| `/api/*`、`/feeds/*.xml|json`、`/sitemap.xml`、`/robots.txt` | 既有產出，不變 | （pipeline 既有） |

所有頁內連結一律使用**根絕對路徑**（`/spectrum/`），不再用 `data-base="../"` 相對路徑。

## 4. 檔案歸屬（同一 working tree、嚴格分檔；不得改別人的檔）

```
scripts/render/                 # 新：Python 渲染套件（純標準函式庫，無 Jinja）
  __init__.py
  shell.py        [phase1]  head()/layout()/nav/footer/icons、esc()、fmt 時間、render_post()、render_avatar()、
                            render_chip()、party/city 色彩 helper、read_json() 等共用工具
  data.py         [phase1]  載入 site/api/*.json、candidates、cities、posts 的統一入口（快取）
  home.py         [home]
  candidate.py    [candidate]   /<city>/<id>/ 與 /source/<id>/
  directory.py    [directory]   /source/、/feeds/、/about/、/404.html
  spectrum.py     [spectrum]    /spectrum/、/spectrum/<slug>/
  policy.py       [policy]      /policy-match/
  status.py       [status]      /status/
  search.py       [home]        /search/ ＋ site/data/search-index.json
scripts/generate_site_pages.py  [phase1 寫骨架；之後只由整合者(主 agent)改] 依序呼叫各 render 模組
site/assets/
  tokens.css      [phase1]
  styles.css      [phase1]  殼、共用元件（見 §5），完全重寫
  shell.js        [phase1]  主題切換、更多選單、相對時間、顯示全文、分享、鍵盤焦點
  pages/home.css / home.js            [home]
  pages/search.css / search.js        [home]
  pages/candidate.css / candidate.js  [candidate]
  pages/directory.css                 [directory]
  pages/spectrum.css / spectrum.js    [spectrum]
  pages/policy.css / policy.js        [policy]
  pages/status.css / status.js        [status]
site/templates/                 # 刪除（改由 Python 直接渲染）— 由 phase1 移除並更新 .gitignore/README 無需
scripts/prerender_pages.py      # 刪除（各頁本身就是 SSR）— phase1 處理，並從 run_pipeline.py 移除呼叫
scripts/generate_seo_pages.py   # 若只負責 sitemap/robots 則保留；若產生舊 HTML 則改為只出 sitemap/robots — phase1 判斷
scripts/build_status_page.py    # status agent 可重構其資料計算部分，HTML 改由 render/status.py 產出
```

- **不要改 `scripts/run_pipeline.py`**、`validate_public_outputs.py`、`publish_github_pages.py`、任何抓取/分類腳本、`data/`。
  需要新增 pipeline 步驟或放寬驗證時，在回報中寫清楚要加什麼，由主 agent 整合。
- 需要新的資料檔（例如每城市 feed bundle）時，在自己的 render 模組內產生到 `site/data/`（已在 .gitignore），
  由 `generate_site_pages.py` 的呼叫順序觸發。
- 頁面 JS 只能依賴 `shell.js` 提供的全域 `window.MO`（見 §6）。

## 5. 共用元件 class 契約（phase1 在 styles.css 實作；其他人直接使用）

殼：`.site-header`（側欄容器）、`.brand`、`.site-nav`、`.nav-item[aria-current=page]`、`.nav-label`、`.nav-more`（`<details>`）、
`.nav-more-menu`、`.topbar-search`、`main.page`、`.page-head`（h1 ＋ `.page-lede` 段落 ＋ 右側 `.page-actions`）、`.site-footer`。

版面：`.container`（max-width `--layout-content`）、`.grid-2` / `.grid-3` / `.grid-4`（自動收合）、`.stack`（垂直 gap）、`.row`（水平 flex, gap 8）。

元件：
- `.card`（surface-raised + border-subtle + radius-lg + padding 16）、`.card-title`、`.card-meta`
- `.stat-tile`（`.stat-value` 大數字、`.stat-label`、`.stat-hint`）
- `.chip`（pill、border）、`.chip-soft`（無框 soft surface）、`.chip[aria-pressed=true]` 選取態、`.chip-count`（chip 內小數字）、
  `.chip-party[data-party]`（前有 6px 圓點）、`.chip-city[data-city]`
- `.btn` / `.btn-primary` / `.btn-ghost` / `.btn-sm`
- `.avatar`（圓形、`data-party` 決定外環色）、`.avatar-lg`、`.avatar-sm`
- `.table`（harmonica Directory 風格：無外框、列分隔線、`th` muted 小字、可 `data-sort`）
- `.badge-status[data-state=ok|warn|error|paused|pending]`
- `.empty`（空狀態）、`.notice`（提示條，`data-tone=info|warn|danger|success`）
- `.filter-row`（label ＋ chips 一列，chumei `.filter-row`）、`.seg`（分段控制）
- `.feed`（單欄貼文列表容器）、`.feed-post`（見下）
- `.story-strip` / `.story-item` / `.story-ring` / `.story-badge` / `.story-name`
- `.feed-cols` / `.feed-col` / `.feed-col-head` / `.col-body` / `.col-filters`（多欄 deck；phase1 只做外框與捲動，行為由 home 實作）
- `.meter`（水平比例條：`.meter-fill` 用 `style="--v:0.15"`）

### 5.1 `render_post()` 輸出結構（phase1 實作於 shell.py；home / candidate / spectrum / search 都用它）

```html
<article class="feed-post" data-id="youtube:xxx" data-candidate="ho-hsin-chun" data-city="taichung"
         data-platform="youtube" data-intent="responsive" data-topics="議會監督,競選" data-ts="1758772806">
  <a class="feed-avatar avatar avatar-sm" data-party="民進黨" href="/taichung/ho-hsin-chun/"><img src="/assets/source-avatars/..webp" alt=""></a>
  <div class="feed-content">
    <header class="feed-head">
      <a class="feed-name" href="/taichung/ho-hsin-chun/">何欣純</a>
      <span class="feed-sep">›</span><a class="feed-city chip-city" data-city="taichung" href="/?city=taichung">臺中</a>
      <time class="feed-time" datetime="2026-09-25T04:00:06+00:00" data-rel>9/25 12:00</time>
      <a class="feed-plat" href="{原文 url}" target="_blank" rel="noopener" aria-label="在 YouTube 開啟原文">{platform svg}</a>
    </header>
    <div class="feed-text" data-clamp>{已 esc、換行轉 <br>、連結轉 <a>}</div>
    <button class="feed-text-toggle" type="button" hidden>顯示全文</button>
    <a class="feed-media" href="{url}" target="_blank" rel="noopener"><img loading="lazy" src=".." alt="" style="aspect-ratio: {w/h 或 4/3}"></a>
    <div class="feed-tags">
      <a class="chip-soft chip-topic" href="/spectrum/{slug}/">議會監督</a> …
      <span class="chip-soft chip-intent" data-intent="responsive" title="{reason}">回應他方觀點 87%</span>
    </div>
    <div class="feed-actions">
      <a class="feed-action" href="{url}" target="_blank" rel="noopener">{external icon}<span>原文</span></a>
      <button class="feed-action btn-share" type="button" data-url="{url}" data-title="…">{share icon}<span>分享</span></button>
      <a class="feed-action" href="/api/posts/{id-safe}.json">{json icon}<span>JSON</span></a>
    </div>
  </div>
</article>
```
- 平台 icon：facebook / instagram / threads / youtube / x / website(globe) / podcast，inline SVG，由 `shell.py:icon(name)` 提供，`shell.js` 不重複定義。
- `feed-text` 預設 clamp 6 行，超過才顯示「顯示全文」（由 shell.js 量測後移除 `hidden`）。
- 圖片：`imageUrl` 為 `assets/feed-images/..` 相對路徑時要轉成根絕對 `/assets/...`。
- 沒有圖片時不輸出 `.feed-media`；沒有 topics 時不輸出 `.feed-tags` 內的議題 chip；`postingIntent` 缺席則不輸出 intent chip。
- **AI 分類標示**：intent chip 的 `title` 放 `reason`；資料頁面（about）說明分類由 AI 完成。

## 6. `shell.js` 提供的全域 `window.MO`

```js
MO.theme.get()/set('dark'|'light'|'system')
MO.relTime(isoOrDate)        // 「3 小時前」「昨天」「9/12」；>7 天顯示 M/D，跨年顯示 YYYY/M/D
MO.fmtTime(iso)              // 「9/25 12:00」Asia/Taipei
MO.esc(str)
MO.postHTML(post, ctx)       // 與 shell.py render_post() 完全同構的前端版本（供 load-more / 搜尋 / 篩選 client 渲染）
MO.icon(name)                // 回傳 svg 字串；名稱與 shell.py 一致
MO.bindPostBehaviors(root)   // 顯示全文、分享（navigator.share → 複製連結 fallback → toast）
MO.toast(msg)
MO.fetchJSON(url)            // 快取
MO.qs / MO.qsa
```
`shell.js` 在 `DOMContentLoaded` 自動：套用 `[data-rel]` 相對時間（並每分鐘更新）、bind 全文/分享、side nav `aria-current`、
`.nav-more` 外點關閉、主題切換 seg。

## 7. 各頁規格

### 7.1 `/` 最新（home）
- 上方 `.story-strip`：13 位候選人頭像（依最新貼文時間排序），外環為政黨色，右下 `.story-badge` = 近 48 小時貼文數（0 不顯示）；
  點擊 → 只顯示該候選人（URL `?candidate=<id>`，deck 變單欄）。
- 主體 `.feed-cols`：桌機為六都六欄（TweetDeck / chumei 樣式，橫向捲動，欄寬 380px，各欄獨立縱向捲動、高度 = 視窗高），
  欄頭：城市圓點 ＋ 城市名 ＋ 篩選鈕（開 `.col-filters`：候選人 chips、平台 chips、議題 chips、動機 seg、關鍵字）＋ 移除欄。
  末端「＋ 加欄」可加回城市欄或「全部」欄、「單一候選人」欄。欄設定存 `localStorage.moDeck`。
- 手機 / 平板：單欄，上方 `.seg` 城市切換（全部 / 六都），篩選面板改為抽屜。
- 資料：SSR 每欄先渲染最新 30 則；client 端由 `site/data/feed/<city>.json`（每城市最新 400 則，home agent 產生）續載；
  「載入更多」按鈕 ＋ IntersectionObserver。
- 支援 URL 參數：`?city=`、`?candidate=`、`?platform=`、`?topic=`、`?intent=`、`?q=`。
- 空狀態、錯誤狀態要有文案。
- 頁面底部小字：資料快照時間（GMT+8）、非官方聲明。

### 7.2 `/<city>/<id>/` 候選人頁（candidate）
- 檔案頭（chumei org 頁風格）：大頭像（政黨外環）、姓名、`chip-party`、`chip-city`、監看帳號 chips（平台 icon ＋ 帳號，連原站）、
  動作：RSS、JSON、「在來源目錄查看帳號驗證」→ `/source/<id>/`。
- 概覽數字 stat tiles：已收錄貼文、近 7 天、主動發文比、回應他方觀點比、最新發文時間。
- 議題比例：`.meter` 列表（由高到低，含關鍵字 chips），點議題 → `/spectrum/<slug>/`。不要圓餅圖。
- 30 天發文節奏：每日小長條（純 CSS/inline SVG，單色）。
- 時間軸 `.feed`：該候選人全部貼文（SSR 前 40 則，其餘由 `/api/posts/<id>.json` 續載，若該檔太大可自己另產 `site/data/candidate/<id>.json` 分頁），
  篩選：平台、議題、動機、關鍵字。
- `/source/<id>/`：該候選人 watchlist 全部帳號表（平台、帳號、角色 account_role、驗證 verification、佐證 evidence、狀態 active、
  已收錄數、最近成功抓取、最新內容時間、目前錯誤），資料來自 `sources.json` ＋ `status.json` v2。

### 7.3 `/source/` 目錄、`/feeds/`、`/about/`、`/404.html`（directory）
- `/source/`：harmonica Directory 風格表格：頭像＋姓名（連候選人頁）、城市、政黨、平台 icon 連結（依 verification 排序，unverified 顯示淡）、
  已收錄、最新內容、監看狀態徽章（來自 status.json）、→ `/source/<id>/`。上方：搜尋、城市/政黨/平台 chips 篩選（純前端，可放在 directory 自己的小段 inline script 或 `pages/directory.js`，若需要 JS 則允許新增該檔）。排序：姓名 / 城市 / 貼文數 / 最新。
- `/feeds/`：全站 RSS、每位候選人 RSS/JSON 列表（依城市分組）、API 端點說明表（`/api/candidates.json` 等）、ICS 無。
- `/about/`：關於（用 README 的內容改寫成公眾能讀的說明）：宗旨、收錄範圍、平台與抓取方式、AI 分類（議題 / 發文動機）如何做與限制、
  刪文保存原則、非官方免責、資料回報（GitHub issue template 連結）、授權（MIT / 貼文著作權屬原作者）、家族站連結（chumei、harmonica、observe.tw）。
- `/404.html`：簡短、有導覽。

### 7.4 `/spectrum/`、`/spectrum/<slug>/`（spectrum）
- 保留現有互動（時間範圍、議題 toggle、動機、排序）但以 tokens 重繪：熱圖用 accent 單色序列，粗框 = 該候選人最高議題；
  手機改為每候選人一張卡（top 5 議題 meter）。表頭議題可點 → 議題頁。
- 議題頁：說明、跨候選人 `.meter` 排行（主動/回應分色為 accent 深淺兩階）、關鍵字雲（chips＋計數）、該議題貼文河道（SSR 30 則，續載用 `topic-index.json` 或自產 `site/data/topic/<slug>.json`）。

### 7.5 `/policy-match/`（policy）
- 保留現有邏輯（讀 `policy-match.json`），重做為逐步問卷（一次一題、進度條、可返回）→ 結果頁：
  依城市分組、每位候選人顯示相符的政策倡議貼文（用 `render_post` 同構卡片或精簡卡）、資料不足者明確顯示「資料不足，不推定立場」。
  結果可用 URL hash 分享（不含個資）。

### 7.6 `/status/`（status）
- 頂部：整體狀態（`.badge-status` ＋ 一句話 ＋ 快照時間 GMT+8 ＋ Status JSON / RSS 按鈕）。
- 系統總覽 stat tiles：監看候選人、監看帳號、已收錄貼文、可抓取來源、目前錯誤、逾期來源。
- 抓取方式卡片（chumei「爬取方式」）：RSSHub IG/Threads/X、Facebook Apify（含預算配速）、YouTube yt-dlp、官網、AI 分類；每卡：狀態徽章、排程來源數、目標頻率、正常/待抓/暫停/錯誤計數、最近成功。
- 來源表（chumei 底部表）：來源/帳號、抓取方式、狀態、最近抓取（嘗試/成功）、下次/頻率、最新內容；狀態與平台 chips 篩選 ＋ 搜尋（前端）。
- 近 7 天錯誤紀錄（含已恢復標示）。
- 遵守 `docs/ingestion-health.md`：不得為了變綠修改資料；只呈現。該文件寫的「不新增前端來源表或搜尋篩選」是上一版的決定；
  本次依 chumei 重製**加入**來源表與前端篩選，但原有四區塊（統計、元件卡片、平台表、錯誤紀錄）的資訊全部保留。status agent 需同步修改該文件那一句。

## 8. SEO / a11y / 效能

- 每頁：`<title>`、`meta description`、canonical、OG（`og:title/description/url/image`＝`/assets/logo.svg` 或候選人頭像）、`lang="zh-Hant"`、
  JSON-LD（首頁 `WebSite`、候選人頁 `Person`＋`ProfilePage`）。
- 全部主要內容 SSR；JS 只增強。無 JS 也要能看到內容與連結。
- 焦點可見、按鈕最小 44px 點擊區、圖片 `alt`、顏色對比 AA。
- CSS/JS 加 `?v=<git short sha 或 build time>` cache-busting（shell.py 提供 `asset_url()`）。
- 不引入任何外部 JS/CSS/字型。

## 8.1 其他硬性限制（來自 ARCH.md）

- SSR HTML **不得**含有字串「載入中」（驗證器會擋）；佔位文案請用「尚無資料」「載入更多」等。
- 驗證器標記（主 agent 會更新 validate_public_outputs.py 對應）：`/` 必含 class `story-strip`、`feed-col`、`feed-post`；`/source/` 必含 `directory-table`；
  `/spectrum/` 必含 `spectrum-table`；`/policy-match/` 必含 `policy-choice`；每個 `/<city>/<id>/` 與 `/source/<id>/` 都要存在；`/spectrum/topic/<slug>/` 保留 meta-refresh 轉址殘根。
- `postedAt` 有三種格式（`Z`、`+00:00`、`+08:00`）且可能為 null；Python 用 `datetime.fromisoformat(s.replace('Z','+00:00'))`，JS 用 `new Date()`；排序一律用 timestamp。
- `spectrum.json`、`topic-index.json` 含已下架候選人 `lin-yi-feng`，一律以 `candidates.json` 的名單過濾。
- 各 render 模組在寫入前先清空自己擁有的輸出目錄（避免下架候選人的殘留檔）。
- 顯示候選人清單時，預設排序在「最新更新 / 貼文數」兩個中性指標間**隨機**擇一（沿用舊站的中立做法），並提供切換。
- `shell.js` 的 `<head>` inline 主題腳本需支援 `?theme=dark|light` 查詢參數（僅本次生效、不寫入 localStorage），供截圖驗收使用。

## 9. 驗收（每個 agent 自己做）

1. `python3 scripts/generate_site_pages.py`（或整合者指定的指令）能無錯產出你的頁面。
2. `python3 -m http.server 8743 --directory site` 後用 `bash tools/shot.sh <path> <out.png> [width]` 截圖桌機 1440 與手機 414，深淺色各一，
   自己看過再回報（截圖放 `/tmp/shots/<agent>/`）。
3. `python3 scripts/validate_public_outputs.py` 不因你的改動新增錯誤（既有的 5 則 YouTube 未分類錯誤是資料問題，可忽略）。
4. 回報：改了哪些檔、需要主 agent 整合的事項（pipeline 步驟、驗證調整）、已知限制。

## 10. 執行環境限制（重要）

- 正式排程機 sky-mini 的直譯器是 **Python 3.9.6**。所有 `scripts/**/*.py` 必須能在 3.9 執行：
  檔頭加 `from __future__ import annotations`；不得使用 `match` 陳述式、`isinstance(x, A | B)`、`zip(strict=)`、
  `dataclass(slots=)`、3.10+ 的 `typing` 執行期功能。`zoneinfo`、`str.removeprefix`、dict `|` 合併可用。
- 網站改由 sky-mini 上的 Caddy 直接以 `published/current` 快照目錄提供（DNS 已改為 A 記錄）；`scripts/publish_local.py` 由主 agent 負責。
