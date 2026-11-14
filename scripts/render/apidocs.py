"""`/api/` — public JSON API reference (endpoints, query parameters, examples).

The query parameters are answered by scripts/api_server.py behind Caddy; the
plain static files work without it. Keep this page in sync with
scripts/api_server.py ENDPOINTS and docs/api.md.
"""

from __future__ import annotations

from . import shell as S

CSS = ["pages/directory.css"]
BASE = S.BASE_URL


def _code(text: str) -> str:
    return f"<code>{S.esc(text)}</code>"


def _pre(text: str) -> str:
    return f'<pre class="api-pre"><code>{S.esc(text)}</code></pre>'


def _table(head: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{S.esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap api-table"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def _link(path: str) -> str:
    return f'<a href="{S.esc(path)}"><code>{S.esc(path)}</code></a>'


POST_FILTER_ROWS = [
    [_code("candidate"), "候選人 ID（逗號分隔可多選），例如 " + _code("chiang-wanan")],
    [_code("city"), "城市：" + "、".join(_code(c) for c in S.CITY_ORDER)],
    [_code("platform"), _code("facebook") + "、" + _code("instagram") + "、" + _code("threads") + "、"
     + _code("youtube") + "、" + _code("x") + "、" + _code("website") + "、" + _code("podcast")],
    [_code("topic"), "議題名稱（中文），例如 " + _code("交通") + "、" + _code("住宅")],
    [_code("intent"), _code("self_initiated") + "（主動發文）或 " + _code("responsive") + "（回應他方觀點）"],
    [_code("since") + " / " + _code("until"), "發文時間區間（ISO 8601；只寫日期時視為臺灣時間 00:00），"
     + _code("until") + " 不含該時刻"],
    [_code("q"), "內文關鍵字，空白分隔、須全部出現（不分大小寫）"],
]

ELECTION_FILTER_ROWS = [
    [_code("county"), "縣市 ID 或中文名，例如 " + _code("taipei") + " 或 " + _code("臺北市")
     + "（ID 見 " + _link("/api/elections/2026/index.json") + "）"],
    [_code("category"), _code("municipal-mayor") + "、" + _code("county-mayor") + "、" + _code("municipal-councilor") + "、"
     + _code("county-councilor") + "、" + _code("township-mayor") + "、" + _code("indigenous-district-chief") + "、"
     + _code("township-rep") + "、" + _code("indigenous-district-rep") + "、" + _code("village-chief")],
    [_code("township"), "鄉鎮市區名（完全相符），例如 " + _code("大安區")],
    [_code("district") + " / " + _code("village"), "選舉區、村里名稱（包含即可）"],
    [_code("districtKey"), "選舉區代碼（完全相符）"],
    [_code("party"), "推薦政黨（包含即可），例如 " + _code("民主進步黨")],
    [_code("incumbent"), _code("true") + " / " + _code("false") + "：是否為 2022 同選區當選人"],
    [_code("number"), "號次"],
    [_code("q"), "姓名、選舉區、鄉鎮、村里、政黨關鍵字（空白分隔須全部出現）"],
    [_code("sort"), _code("number") + " 或 " + _code("name") + "（在同一縣市、類別、選舉區內排序）"],
]


def render(data) -> None:
    example_latest = f"{BASE}/api/latest.json?limit=10"
    sections = [
        ("overview", "概要",
         "<p>本站所有資料都以 JSON（以及 RSS／CSV）公開，可免費使用、不需金鑰，並已開啟 CORS"
         f"（{_code('Access-Control-Allow-Origin: *')}），網頁前端可直接 {_code('fetch')}。</p>"
         "<p>不加參數時，每個端點回傳完整的靜態檔；加上 <strong>查詢參數</strong>（例如 "
         f"{_code('?limit=10')}）時由 API 服務即時篩選、切片後回傳，結構與靜態檔相同。"
         "資料每 6 小時更新一次（臺灣時間 0、6、12、18 時）。</p>"
         + _pre(f"curl '{example_latest}'")),
        ("params", "共通參數（數量、分頁、欄位）",
         "<p>以下參數適用所有「列表」端點：</p>"
         + _table(["參數", "說明"], [
             [_code("limit"), "最多回傳幾筆（≥ 0 的整數）。不給則回傳全部"],
             [_code("offset"), "跳過前幾筆，用於分頁（預設 0）"],
             [_code("fields"), "每筆只保留指定欄位，逗號分隔，例如 " + _code("fields=id,text,url,postedAt")],
         ])
         + "<p>回應會保留原本欄位，另外加上：</p>"
         + _table(["欄位", "說明"], [
             [_code("count"), "本次實際回傳筆數"],
             [_code("total"), "符合篩選條件的總筆數（切片前）"],
             [_code("offset") + " / " + _code("limit"), "本次使用的分頁參數"],
             [_code("next"), "下一頁的路徑（含原本參數）；沒有下一頁時為 " + _code("null")],
         ])),
        ("posts", "候選人貼文",
         "<p>六都市長候選人官方帳號的公開貼文，皆依發文時間由新到舊。</p>"
         + _table(["端點", "內容"], [
             [_link("/api/latest.json"), "全站最新 100 則（完整欄位）"],
             [_code("/api/posts.json"), "<strong>全部</strong>貼文（完整欄位）；只有加參數時可用，請務必帶 " + _code("limit")],
             [_code("/api/posts/<候選人ID>.json"), "單一候選人全部貼文，例如 " + _link("/api/posts/chiang-wanan.json")],
             [_code("/feeds/<候選人ID>.json"), "單一候選人最近 50 則（RSS 的 JSON 版）"],
             [_link("/api/topic-index.json"), "全部貼文的精簡索引（議題分數、動機、時間）"],
         ])
         + "<p>以上端點都可再加篩選參數：</p>"
         + _table(["參數", "說明"], POST_FILTER_ROWS)
         + "<p>每則貼文的主要欄位：" + "、".join(_code(f) for f in (
             "id", "candidateId", "platform", "postedAt", "text", "url", "imageUrl", "topics", "topicScores",
             "postingIntent", "keywords", "classification")) + "。"
         + _code("imageUrl") + " 為站內相對路徑，請自行加上 " + _code(BASE + "/") + "；本地圖片副本約 60 天後移除。</p>"),
        ("elections", "2026 地方選舉候選人",
         "<p>九合一全部九類候選人與號次，只用中選會與各選委會公告。</p>"
         + _table(["端點", "內容"], [
             [_code("/api/elections/2026/candidates.json"), "全部候選人的<strong>平面列表</strong>（可篩選、分頁）；"
              "每筆含 " + _code("county") + "、" + _code("countyLabel") + "、" + _code("category") + "、"
              + _code("categoryLabel") + "、" + _code("township") + "、" + _code("district") + "、" + _code("village") + "、"
              + _code("number") + "、" + _code("name") + "、" + _code("party") + "、" + _code("incumbent") + " 與官方來源網址"],
             [_link("/api/elections/2026/index.json"), "總數、各縣市與各類別統計、縣市 ID 對照"],
             [_code("/api/elections/2026/<縣市ID>.json"), "單一縣市依類別→選舉區分組的完整資料（巢狀，不接受參數）"],
             [_link("/api/elections/2026/candidates.csv"), "全部候選人 CSV"],
             [_link("/api/elections/2026/reconciliation.json"), "與官方總數的對帳報告"],
             [_link("/api/elections/2026/sources.json"), "使用到的官方來源與 sha256"],
         ])
         + "<p>" + _code("candidates.json") + " 可用的篩選參數：</p>"
         + _table(["參數", "說明"], ELECTION_FILTER_ROWS)),
        ("other", "其他列表端點",
         _table(["端點", "列表欄位", "可用篩選"], [
             [_link("/api/candidates.json"), _code("candidates"), _code("city")],
             [_link("/api/sources.json"), _code("sources"), _code("candidate") + "、" + _code("city")],
             [_link("/api/spectrum.json"), _code("candidates"), _code("candidate") + "、" + _code("city")],
             [_link("/api/status.json"), _code("sources"), _code("candidate") + "、" + _code("platform")],
             [_link("/api/cities.json"), _code("cities"), "—"],
         ])
         + "<p>非列表端點（例如 " + _link("/api/policy-match.json") + "、" + _link("/api/topic-details.json") + "、"
         + _link("/api/pipeline-runtime.json") + "）只提供完整檔案，帶參數會回 400。</p>"),
        ("examples", "範例",
         "<p>最新 10 則貼文，只取必要欄位：</p>"
         + _pre(f"{BASE}/api/latest.json?limit=10&fields=candidateId,platform,postedAt,text,url")
         + "<p>全部貼文中，臺北市候選人 11 月以後談交通的前 20 則：</p>"
         + _pre(f"{BASE}/api/posts.json?city=taipei&topic=交通&since=2026-11-01&limit=20")
         + "<p>蔣萬安最新 5 則 Facebook 貼文：</p>"
         + _pre(f"{BASE}/api/posts/chiang-wanan.json?platform=facebook&limit=5")
         + "<p>臺北市長候選人與號次：</p>"
         + _pre(f"{BASE}/api/elections/2026/candidates.json?county=taipei&category=municipal-mayor&sort=number")
         + "<p>新竹市議員候選人，每頁 50 筆的第 2 頁：</p>"
         + _pre(f"{BASE}/api/elections/2026/candidates.json?county=hsinchu-city&category=county-councilor&limit=50&offset=50")
         + "<p>JavaScript：</p>"
         + _pre("const res = await fetch('" + BASE + "/api/latest.json?limit=5');\n"
                "const { posts, total } = await res.json();\n"
                "posts.forEach(p => console.log(p.candidateId, p.postedAt, p.url));")
         + "<p>中文參數值請做 URL 編碼（瀏覽器與 " + _code("fetch") + " 會自動處理；" + _code("curl")
         + " 可用 " + _code("--get --data-urlencode 'topic=交通'") + "）。</p>"),
        ("errors", "錯誤與限制",
         "<p>參數格式錯誤、端點不支援的參數，回傳 HTTP 400 與 JSON："
         + _code('{"error": "…", "status": 400, "allowed": [...]}') + "；找不到檔案回 404。"
         "未知的參數名稱（例如快取用的 " + _code("?v=") + "）會被忽略。</p>"
         "<p>沒有速率限制，但請合理使用並自行快取（回應帶 " + _code("Cache-Control: max-age=60") + "）；"
         "資料一天只更新四次，頻繁輪詢沒有幫助。</p>"),
        ("rss", "RSS",
         "<p>每位候選人一條 RSS：" + _code("/feeds/<候選人ID>.xml") + "；2026 候選人名單更新："
         + _link("/feeds/elections-2026.xml") + "。完整清單見<a href=\"/feeds/\">RSS 訂閱</a>。</p>"),
        ("license", "授權與引用",
         "<p>候選人名單來自選委會公告；貼文著作權屬原作者，轉載請連回原文（每則都有 " + _code("url") + "）。"
         "議題與發文動機為 AI 分類，可能有誤。引用時請註明「2026 地方選舉官方來源觀測站（mayor2026.observe.tw）」。"
         f'資料問題請到 <a href="{S.REPORT_URL}" target="_blank" rel="noopener">GitHub</a> 回報。</p>'),
    ]
    toc = "".join(f'<a class="about-toc-link" href="#{sid}">{S.esc(title)}</a>' for sid, title, _ in sections)
    prose = "".join(f'<section id="{sid}" class="about-sec"><h2>{S.esc(title)}</h2>{html}</section>'
                    for sid, title, html in sections)
    facts = (
        '<aside class="about-facts" aria-label="快速開始">'
        '<section class="card"><h2 class="about-side-title">快速開始</h2>'
        f'<p class="small">在任何列表端點加上 {_code("?limit=N")} 就能指定回傳數量，'
        f'{_code("offset")} 分頁、{_code("fields")} 精簡欄位。</p>'
        f'<a class="btn btn-sm" href="/api/latest.json?limit=5">試試最新 5 則</a></section>'
        '<section class="card"><h2 class="about-side-title">基本資訊</h2><dl class="about-dl">'
        '<div><dt>金鑰</dt><dd>不需要</dd></div>'
        '<div><dt>CORS</dt><dd>開放</dd></div>'
        '<div><dt>更新頻率</dt><dd>每 6 小時（0、6、12、18 時）</dd></div>'
        "</dl></section>"
        "</aside>"
    )
    body = (
        S.page_head("開放資料 API", "候選人貼文、2026 地方選舉候選人名單與號次的 JSON 端點、查詢參數與使用範例。",
                    eyebrow="開發者")
        + '<div class="about-layout">'
        + f'<nav class="about-toc" aria-label="本頁目錄"><p class="about-side-title">本頁目錄</p>{toc}</nav>'
        + f'<div class="about prose">{prose}</div>'
        + facts + "</div>"
    )
    jsonld = {"@context": "https://schema.org", "@type": "TechArticle", "name": "開放資料 API",
              "url": S.canonical("/api/"), "inLanguage": "zh-Hant",
              "isPartOf": {"@type": "WebSite", "name": S.SITE_NAME, "url": S.BASE_URL + "/"}}
    html = S.layout("api", "開放資料 API",
                    "2026 地方選舉官方來源觀測站的 JSON API：端點、limit／offset／fields 等查詢參數、篩選條件與範例。",
                    "/api/", body, extra_css=CSS, jsonld=jsonld)
    S.write_page("/api/", html)
