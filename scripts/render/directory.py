"""/source/ (candidate & account directory), /feeds/, /about/ and /404.html.

Outputs owned here: site/source/index.html (NOT site/source/<id>/ — that is
render/candidate.py), site/feeds/index.html (the rest of site/feeds/ is written
by generate_rss_feeds.py), site/about/, site/404.html.
"""

from __future__ import annotations

import random
import shutil
from collections import Counter
from typing import Any

from . import shell as S

CSS = ["pages/directory.css"]
JS = ["pages/directory.js"]

VERIFICATION_RANK = {"first_party": 0, "cross_ref": 1, "unverified": 2}
VERIFICATION_LABELS = {"first_party": "官方直連", "cross_ref": "交叉查證", "unverified": "未驗證"}
ROLE_RANK = {"campaign": 0, "incumbent": 0, "personal": 1, "affiliated": 2, "party": 3}
ROLE_LABELS = {"campaign": "競選", "incumbent": "現任公職", "personal": "個人", "affiliated": "關聯", "party": "政黨"}
# Filter chips: platform key → label (LINE 官方帳號 / 社群 share one chip).
PLATFORM_FILTERS = [
    ("facebook", "Facebook"), ("instagram", "Instagram"), ("threads", "Threads"), ("youtube", "YouTube"),
    ("x", "X"), ("website", "官網"), ("podcast", "Podcast"), ("line", "LINE"), ("tiktok", "TikTok"),
]
SORTS = [("latest", "最新更新"), ("posts", "貼文數"), ("name", "姓名"), ("city", "城市")]
NEUTRAL_SORTS = ("latest", "posts")

API_ENDPOINTS = [
    ("/api/candidates.json", "候選人名單：姓名、城市、政黨、頭像、各平台代表帳號、已收錄貼文數與最新發文時間。"),
    ("/api/sources.json", "候選人名單加上全部監看帳號（平台、網址、帳號性質、驗證等級）。"),
    ("/api/cities.json", "六都與各城市候選人 ID，順序固定。"),
    ("/api/latest.json", "全站最新 100 則貼文。"),
    ("/api/posts/<id>.json", "單一候選人的全部已收錄貼文（含議題、發文動機與 AI 分類資訊），新到舊。"),
    ("/api/spectrum.json", "每位候選人各議題的發文比例（不含「生活」）。"),
    ("/api/topic-index.json", "所有貼文的議題分數與發文動機索引，供跨候選人比較。"),
    ("/api/topic-details.json", "各議題、各候選人的關鍵字出現次數。"),
    ("/api/policy-match.json", "議題選擇器的題目、選項與候選人政策議程向量（附佐證貼文）。"),
    ("/api/qualitative-summary.json", "全站發文動機統計（主動發文／回應他方觀點）。"),
    ("/api/status.json", "資料管線與每個監看來源的抓取狀態。"),
]


def _plat_key(platform: str | None) -> str:
    p = platform or "website"
    return "line" if p.startswith("line") else p


def _account_sort_key(acc: dict[str, Any]) -> tuple:
    return (VERIFICATION_RANK.get(acc.get("verification"), 3), ROLE_RANK.get(acc.get("role"), 4))


def _account_link(acc: dict[str, Any]) -> str:
    platform = acc.get("platform") or "website"
    plabel = S.PLATFORM_LABELS.get(platform, platform)
    handle = acc.get("handle") if acc.get("handle") not in (None, "", "unknown") else None
    who = acc.get("displayName") or (f"@{handle}" if handle and platform not in ("website", "podcast") else handle)
    ver = acc.get("verification") or "unverified"
    parts = [plabel] + ([who] if who else []) + [
        f"{ROLE_LABELS.get(acc.get('role'), acc.get('role') or '')}・{VERIFICATION_LABELS.get(ver, ver)}"]
    title = "｜".join(p for p in parts if p)
    return (f'<a class="acct" data-verification="{S.esc(ver)}" href="{S.esc(acc.get("url") or "#")}" '
            f'target="_blank" rel="noopener" title="{S.esc(title)}" aria-label="{S.esc(title)}">'
            f'{S.icon(platform)}</a>')


def _status_summary(rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    """(state, label, title) for a candidate's status.json sources."""
    watched = [r for r in rows if r.get("fetchable") and r.get("active", True)]
    if not rows:
        return "pending", "尚無資料", "status.json 中沒有這位候選人的來源紀錄"
    if not watched:
        return "paused", "僅連結", "目前沒有可自動抓取的來源"
    counts = Counter(r.get("status") for r in watched)
    errors = counts.get("error", 0)
    late = counts.get("overdue", 0) + counts.get("blocked", 0)
    detail = f"可抓取來源 {len(watched)} 個"
    bits = [f"抓取失敗 {errors}" if errors else "", f"逾期 {counts.get('overdue', 0)}" if counts.get("overdue") else "",
            f"冷卻 {counts.get('blocked', 0)}" if counts.get("blocked") else ""]
    bits = [b for b in bits if b]
    title = detail + ("：" + "、".join(bits) if bits else "，皆正常")
    if errors:
        return "error", f"{errors} 個失敗", title
    if late:
        return "warn", f"{late} 個延遲", title
    return "ok", "正常", title


def _time_cell(iso: str | None) -> str:
    if not S.parse_ts(iso):
        return '<span class="muted">—</span>'
    return (f'<time datetime="{S.esc(iso)}" data-rel title="{S.esc(S.fmt_time_tpe(iso, True))}">'
            f'{S.esc(S.rel_time_tpe(iso))}</time>')


# ---------------------------------------------------------------------------
# /source/
# ---------------------------------------------------------------------------

def _chip_group(label: str, key: str, options: list[tuple[str, str, dict[str, Any]]]) -> str:
    chips = [S.render_chip("全部", pressed=True, attrs={"data-filter": key, "data-value": ""})]
    for value, text, extra in options:
        chips.append(S.render_chip(text, pressed=False, attrs={"data-filter": key, "data-value": value}, **extra))
    return (f'<div class="filter-row" role="group" aria-label="{S.esc(label)}">'
            f'<span class="filter-label">{S.esc(label)}</span><div class="chips">{"".join(chips)}</div></div>')


def render_source_index(data) -> None:
    sources = data.sources_by_id
    status_rows: dict[str, list[dict[str, Any]]] = {}
    for row in (data.status or {}).get("sources") or []:
        status_rows.setdefault(row.get("candidateId"), []).append(row)

    city_index = {slug: i for i, slug in enumerate(S.CITY_ORDER)}
    parties: list[str] = []
    platforms_present: set[str] = set()
    rows = []
    total_accounts = 0
    for c in data.candidates:
        cid = c["id"]
        accounts = sorted((sources.get(cid) or {}).get("accounts") or [], key=_account_sort_key)
        total_accounts += len(accounts)
        plats = sorted({_plat_key(a.get("platform")) for a in accounts})
        platforms_present.update(plats)
        party = c.get("party") or "無黨籍"
        if party not in parties:
            parties.append(party)
        state, slabel, stitle = _status_summary(status_rows.get(cid, [])) if data.status else \
            ("pending", "尚無資料", "status.json 不存在")
        city = c.get("city") or ""
        href = f"/{city}/{cid}/"
        handles = " ".join(filter(None, [(a.get("handle") or "") + " " + (a.get("displayName") or "") for a in accounts]))
        search = " ".join([c.get("name") or "", cid, S.city_label(city, False), party, handles]).lower()
        acct_html = "".join(_account_link(a) for a in accounts) or '<span class="muted">—</span>'
        rows.append(
            f'<tr data-name="{S.esc(c.get("name"))}" data-city="{S.esc(city)}" data-city-index="{city_index.get(city, 99)}" '
            f'data-party="{S.esc(party)}" data-platforms="{" ".join(plats)}" data-posts="{int(c.get("postCount") or 0)}" '
            f'data-ts="{S.epoch(c.get("latestPostAt"))}" data-search="{S.esc(search)}">'
            f'<td class="col-name"><div class="table-identity">{S.render_avatar(c, "md", href=href)}'
            f'<div class="dir-name"><a href="{href}">{S.esc(c.get("name"))}</a>'
            f'<span class="dir-sub">{len(accounts)} 個公開帳號</span>'
            f'<span class="dir-sub dir-phone-meta"><span class="chip-city" data-city="{S.esc(city)}">'
            f'{S.esc(S.city_label(city))}</span>・{S.esc(party)}・{len(accounts)} 個帳號</span></div></div></td>'
            f'<td class="col-city">{S.render_chip(S.city_label(city), city=city, soft=True)}</td>'
            f'<td class="col-party">{S.render_chip(party, party=party, soft=True)}</td>'
            f'<td class="col-accts"><div class="acct-list">{acct_html}</div></td>'
            f'<td class="num col-posts"><span class="dir-k">已收錄</span>{int(c.get("postCount") or 0):,}</td>'
            f'<td class="num col-latest"><span class="dir-k">最新</span>{_time_cell(c.get("latestPostAt"))}</td>'
            f'<td class="col-status"><span title="{S.esc(stitle)}">{S.render_badge(state, slabel)}</span></td>'
            f'<td class="col-go"><a class="btn btn-sm btn-ghost dir-go" href="/source/{S.esc(cid)}/" '
            f'aria-label="{S.esc(c.get("name"))} 的帳號明細">明細{S.icon("chevron", "icon icon-go")}</a></td>'
            "</tr>"
        )

    default_sort = random.choice(NEUTRAL_SORTS)
    rows_sorted = _sort_rows_ssr(data, rows, default_sort)

    lede = (
        f"六都 {len(data.candidates)} 位候選人、{total_accounts} 個監看中的公開帳號。"
        "帳號依可信度排序：<b>官方直連</b>＝候選人官網或官方帳號直接連結；"
        "<b>交叉查證</b>＝由多個公開線索合理確認；<span class=\"acct-legend-dim\">未驗證</span>＝"
        "尚無第一手指認，以淡色顯示，僅供參考。"
    )
    actions = (f'<a class="btn btn-sm" href="/feeds/">{S.icon("rss")}訂閱</a>'
               f'<a class="btn btn-sm" href="/api/sources.json">{S.icon("json")}JSON</a>')
    city_opts = [(slug, S.city_label(slug), {"city": slug}) for slug in S.CITY_ORDER
                 if any(c.get("city") == slug for c in data.candidates)]
    party_opts = [(p, p, {"party": p}) for p in parties]
    plat_opts = [(k, lbl, {"icon_name": k}) for k, lbl in PLATFORM_FILTERS if k in platforms_present]
    sort_seg = "".join(
        f'<button type="button" data-sort-key="{k}" aria-pressed="{"true" if k == default_sort else "false"}">{lbl}</button>'
        for k, lbl in SORTS
    )
    head_cells = [
        ("候選人", "name", "col-name"), ("城市", "city", "col-city"), ("政黨", None, "col-party"),
        ("公開帳號", None, "col-accts"), ("已收錄", "posts", "num col-posts"), ("最新內容", "latest", "num col-latest"),
        ("監看狀態", None, "col-status"), ('<span class="sr-only">明細</span>', None, "col-go"),
    ]
    ths = "".join(
        f'<th class="{cls}" scope="col"'
        + (f' data-sort="{key}"' + (' aria-sort="descending"' if key == default_sort else "") + ' tabindex="0"' if key else "")
        + f">{label}</th>"
        for label, key, cls in head_cells
    )
    body = (
        S.page_head("候選人與公開來源", lede, actions)
        + '<section class="dir-controls" aria-label="篩選與排序">'
        + '<div class="dir-search"><label class="sr-only" for="dir-q">搜尋候選人或帳號</label>'
        + f'{S.icon("search", "icon dir-search-icon")}'
        + '<input class="input" id="dir-q" type="search" placeholder="搜尋姓名、城市、政黨或帳號…" autocomplete="off"></div>'
        + '<div class="dir-filters">'
        + _chip_group("城市", "city", city_opts) + _chip_group("政黨", "party", party_opts)
        + _chip_group("平台", "platform", plat_opts)
        + "</div>"
        + '<div class="dir-toolbar"><p class="dir-count small muted" aria-live="polite">'
        + f'共 <b class="num" data-count>{len(rows)}</b> 位候選人</p>'
        + f'<div class="dir-sort"><span class="small muted">排序</span><div class="seg" role="group" aria-label="排序">{sort_seg}</div></div>'
        + "</div></section>"
        + '<div class="table-wrap"><table class="table directory-table" data-default-sort="' + default_sort + '">'
        + '<caption class="sr-only">六都市長候選人與公開帳號目錄</caption>'
        + f"<thead><tr>{ths}</tr></thead><tbody>{''.join(rows_sorted)}</tbody></table></div>"
        + '<div class="dir-empty" hidden>'
        + S.render_empty("沒有符合條件的候選人", "試著清除搜尋字詞或篩選條件。",
                         '<button class="btn btn-sm" type="button" data-reset>清除篩選</button>')
        + "</div>"
        + '<p class="snapshot">預設排序在「最新更新」與「貼文數」之間隨機選擇，排列順序不代表任何立場。'
        + f'監看狀態取自 <a href="/status/">資料狀態</a>；資料快照 {S.esc(S.fmt_time_tpe(data.generated_at.isoformat(), True))}（GMT+8）。</p>'
    )
    jsonld = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": "候選人與公開來源",
        "url": S.canonical("/source/"), "inLanguage": "zh-Hant",
        "hasPart": [{"@type": "Person", "name": c.get("name"), "url": S.canonical(f"/{c.get('city')}/{c['id']}/")}
                    for c in data.candidates],
    }
    html = S.layout("directory", "候選人與公開來源",
                    f"六都 {len(data.candidates)} 位市長候選人的官方公開帳號目錄：平台、驗證等級、已收錄貼文數與監看狀態。",
                    "/source/", body, extra_css=CSS, extra_js=JS, jsonld=jsonld)
    S.write_page("/source/", html)


def _sort_rows_ssr(data, rows: list[str], key: str) -> list[str]:
    cands = data.candidates
    if key == "posts":
        order = sorted(range(len(cands)), key=lambda i: -(cands[i].get("postCount") or 0))
    else:
        order = sorted(range(len(cands)), key=lambda i: -S.epoch(cands[i].get("latestPostAt")))
    return [rows[i] for i in order]


# ---------------------------------------------------------------------------
# /feeds/
# ---------------------------------------------------------------------------

def _copy_btn(path: str, what: str) -> str:
    return (f'<button class="btn btn-sm btn-icon btn-ghost" type="button" data-copy="{S.esc(path)}" '
            f'aria-label="複製{S.esc(what)}網址" title="複製網址">{_COPY_SVG}</button>')


_COPY_SVG = ('<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
             '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2.2"/>'
             '<path d="M15.5 8.5V6.2A2.2 2.2 0 0 0 13.3 4H6.2A2.2 2.2 0 0 0 4 6.2v7.1a2.2 2.2 0 0 0 2.2 2.2h2.3"/></svg>')


def _feed_cand(c: dict[str, Any]) -> str:
    cid, name = c["id"], c.get("name") or c["id"]
    href = f"/{c.get('city')}/{cid}/"
    xml, jsn = f"/feeds/{cid}.xml", f"/feeds/{cid}.json"
    return (
        f'<li class="sub-cand">{S.render_avatar(c, "sm", href=href, label=name)}'
        f'<div class="sub-cand-text"><a class="sub-cand-name" href="{href}">{S.esc(name)}</a>'
        f'<span class="xs muted">{S.esc(c.get("party") or "無黨籍")}・{int(c.get("postCount") or 0):,} 則</span></div>'
        f'<div class="sub-cand-actions"><a class="btn btn-sm" href="{xml}" aria-label="{S.esc(name)} RSS">RSS</a>'
        f'<a class="btn btn-sm btn-ghost" href="{jsn}" aria-label="{S.esc(name)} JSON">JSON</a>'
        f'{_copy_btn(xml, name + " RSS ")}</div></li>'
    )


def render_feeds(data) -> None:
    site_feed = (
        '<div class="grid-2">'
        '<div class="card sub-card"><div class="sub-card-head">'
        f'<span class="sub-card-icon">{S.icon("rss")}</span><div><p class="card-title">全站更新 RSS</p>'
        '<p class="card-meta">六都所有候選人最新 100 則貼文</p></div></div>'
        '<div class="sub-url"><code class="mono">/feeds/updates.xml</code>'
        f'{_copy_btn("/feeds/updates.xml", "全站 RSS ")}</div>'
        f'<a class="btn btn-sm btn-primary" href="/feeds/updates.xml">{S.icon("rss")}開啟 RSS</a></div>'
        '<div class="card sub-card"><div class="sub-card-head">'
        f'<span class="sub-card-icon">{S.icon("json")}</span><div><p class="card-title">全站更新 JSON</p>'
        '<p class="card-meta">同一份內容的 JSON 版本，方便程式讀取</p></div></div>'
        '<div class="sub-url"><code class="mono">/feeds/updates.json</code>'
        f'{_copy_btn("/feeds/updates.json", "全站 JSON ")}</div>'
        f'<a class="btn btn-sm" href="/feeds/updates.json">{S.icon("json")}開啟 JSON</a></div>'
        "</div>"
    )
    city_cards = []
    for city in data.cities:
        members = [data.by_id[i] for i in city["candidateIds"] if i in data.by_id]
        if not members:
            continue
        items = "".join(_feed_cand(c) for c in members)
        city_cards.append(
            f'<section class="card sub-city" data-city="{S.esc(city["id"])}" aria-label="{S.esc(city.get("label"))}">'
            f'<h3 class="sub-city-title"><span class="feed-col-dot"></span>{S.esc(S.city_label(city["id"], False))}</h3>'
            f'<ul class="sub-cand-list">{items}</ul></section>'
        )
    api_rows = "".join(
        f'<tr><td class="api-path"><a class="mono" href="{S.esc(path.replace("<id>", data.candidates[0]["id"]))}">'
        f'{S.esc(path)}</a></td><td>{S.esc(desc)}</td>'
        f'<td class="api-copy">{_copy_btn(path.replace("<id>", data.candidates[0]["id"]), path + " ")}</td></tr>'
        for path, desc in API_ENDPOINTS
    )
    body = (
        S.page_head(
            "訂閱與資料下載",
            "把 RSS 網址貼進 Feedly、Inoreader、NetNewsWire 等閱讀器，就能追蹤候選人的新發文。"
            "每條 RSS 收錄最新 50 則；需要完整紀錄請用 JSON API。",
            f'<a class="btn btn-sm" href="/about/#license">{S.icon("about")}授權說明</a>',
        )
        + f'<section class="section-first" aria-labelledby="h-site"><div class="section-head"><h2 id="h-site">全站</h2></div>{site_feed}</section>'
        + '<section class="section" aria-labelledby="h-cand"><div class="section-head"><h2 id="h-cand">各候選人</h2>'
        + '<span class="small muted">依城市分組・<code class="mono">/feeds/&lt;id&gt;.xml</code> 與 <code class="mono">.json</code></span></div>'
        + f'<div class="grid-2 sub-cities">{"".join(city_cards)}</div></section>'
        + '<section class="section" aria-labelledby="h-api"><div class="section-head"><h2 id="h-api">JSON API</h2></div>'
        + '<p class="small muted api-lede">靜態 JSON，無需金鑰，可直接下載；每次資料更新時重新產生。'
        + '<code class="mono">&lt;id&gt;</code> 為候選人 ID，可在 <a href="/api/candidates.json">candidates.json</a> 查到，範例連結以第一位候選人示範。</p>'
        + '<div class="table-wrap"><table class="table api-table"><caption class="sr-only">JSON API 端點</caption>'
        + '<thead><tr><th scope="col">端點</th><th scope="col">內容</th><th scope="col"><span class="sr-only">複製</span></th></tr></thead>'
        + f"<tbody>{api_rows}</tbody></table></div>"
        + '<div class="notice" data-tone="info">' + S.icon("about")
        + '<p>程式碼以 MIT 授權釋出；貼文內容的著作權屬原作者，本站只做索引並連回原文。引用資料時請註明「2026 市長官方來源觀測站」並附上原文連結；'
        + '議題與發文動機為 AI 分類結果，可能有誤。</p></div></section>'
    )
    html = S.layout("feeds", "訂閱與資料下載",
                    "六都市長候選人官方發文的 RSS 與 JSON 訂閱：全站更新、每位候選人各一條，並附公開 JSON API 說明。",
                    "/feeds/", body, extra_css=CSS, extra_js=JS)
    S.write_page("/feeds/", html)


# ---------------------------------------------------------------------------
# /about/
# ---------------------------------------------------------------------------

def render_about(data) -> None:
    shutil.rmtree(S.SITE_ROOT / "about", ignore_errors=True)
    n_cand = len(data.candidates)
    n_acct = sum(len(s.get("accounts") or []) for s in data.sources)
    n_posts = sum(int(c.get("postCount") or 0) for c in data.candidates)
    models: Counter = Counter()
    for cid in data.by_id:
        for p in data.posts_for(cid):
            m = (p.get("classification") or {}).get("model")
            if m:
                models[m] += 1
    model_list = "、".join(f"<code>{S.esc(m)}</code>" for m, _ in models.most_common())
    model_note = f"目前資料中使用過的模型有 {model_list}；" if model_list else ""
    ext = ' target="_blank" rel="noopener"'

    sections = [
        ("purpose", "宗旨",
         "<p>本站把六都市長候選人在官方帳號上的公開發文集中在一起，依議題與發文動機整理，"
         "方便用同一把尺比較候選人說了什麼。每則貼文都連回原文；本站不改寫內容，也不做民調或立場推定。</p>"),
        ("scope", "收錄範圍",
         f"<p>目前收錄六都 {n_cand} 位候選人、{n_acct} 個公開帳號，已收錄 {n_posts:,} 則貼文。"
         "平台包括 Facebook、Instagram、Threads、YouTube、X、競選官網與 Podcast；LINE 與 TikTok 沒有可穩定讀取的公開時間軸，只列出連結。"
         '每個帳號都標示驗證等級，完整清單見<a href="/source/">候選人目錄</a>。</p>'),
        ("method", "資料怎麼來",
         "<p>系統每天定時讀取公開內容：Instagram、Threads、X 透過 RSSHub，Facebook 透過 Apify，"
         "YouTube 使用 yt-dlp，競選官網則逐站撰寫讀取程式。只讀公開內容，不使用私人資料。"
         '各來源的最新狀態見<a href="/status/">資料狀態</a>。</p>'),
        ("ai", "AI 分類與限制",
         f"<p>每則貼文由 AI 標上議題（交通、住宅、社福等 15 類，可複選）與發文動機（「主動發文」或「回應他方觀點」）。"
         "判為回應的貼文會再經第二次 AI 檢查。"
         f"{model_note}每則貼文實際使用的模型與規範版本，以貼文 JSON 的 <code>classification</code> 欄位為準。</p>"
         "<p>AI 可能誤判，例如反諷、圖片為主或很短的貼文；分類僅供參考，請以原文為準。</p>"),
        ("archive", "刪文也會保留",
         "<p>刪文本身也是值得留存的紀錄。原始資料只增不改，已收錄的貼文不會因原文刪除而消失；圖片的本地副本則會定期清除。</p>"),
        ("neutrality", "中立做法",
         "<p>列出候選人時，預設順序在「最新更新」與「貼文數」之間隨機選擇；介面主色不使用任何政黨代表色，政黨色只用於頭像外框等小面積標示。</p>"),
        ("disclaimer", "非官方聲明",
         "<p>本站與任何候選人、政黨、競選團隊或選務機關無關，也未接受其委託或資助。</p>"),
        ("report", "資料回報",
         f'<p>發現帳號錯誤、漏收或想建議新增候選人，請到 <a href="{S.REPORT_URL}"{ext}>GitHub Issue</a> 填寫表單。'
         "回報內容會公開，請只提供公開可查的資料。</p>"),
        ("license", "授權",
         f'<p>網站程式碼以 <a href="{S.GITHUB_URL}/blob/main/LICENSE"{ext}>MIT 授權</a>開源。'
         "貼文文字、圖片與影片的著作權屬原作者；轉載請連回原文。</p>"),
        ("family", "觀測站家族",
         f'<p>同系列的公開資料觀測站：<a href="https://chumei.observe.tw/"{ext}>竹梅活動觀測站</a>、'
         f'<a href="https://harmonica.observe.tw/"{ext}>Harmonica Observatory</a>，總覽見 '
         f'<a href="https://observe.tw/"{ext}>observe.tw</a>。</p>'),
        ("contact", "聯絡與原始碼",
         f'<p>原始碼、問題回報與開發紀錄都在 <a href="{S.GITHUB_URL}"{ext}>GitHub</a>。'
         '想自行分析資料，可使用<a href="/feeds/">RSS 與 JSON API</a>。</p>'),
    ]
    toc = "".join(f'<a class="chip-soft" href="#{sid}">{S.esc(title)}</a>' for sid, title, _ in sections)
    prose = "".join(f'<section id="{sid}" class="about-sec"><h2>{S.esc(title)}</h2>{html}</section>'
                    for sid, title, html in sections)
    body = (
        '<div class="reading about">'
        + S.page_head("關於本站", "2026 市長官方來源觀測站是獨立、非官方的公開資料專案，"
                      "整理六都市長候選人官方帳號的公開發文。")
        + f'<nav class="about-toc" aria-label="本頁目錄">{toc}</nav>'
        + f'<div class="prose">{prose}</div></div>'
    )
    jsonld = {"@context": "https://schema.org", "@type": "AboutPage", "name": "關於本站",
              "url": S.canonical("/about/"), "inLanguage": "zh-Hant",
              "isPartOf": {"@type": "WebSite", "name": S.SITE_NAME, "url": S.BASE_URL + "/"}}
    html = S.layout("about", "關於本站",
                    "本站的宗旨、收錄範圍、資料取得方式、AI 分類限制、刪文保存原則、中立做法與授權說明。",
                    "/about/", body, extra_css=CSS, jsonld=jsonld)
    S.write_page("/about/", html)


# ---------------------------------------------------------------------------
# /404.html
# ---------------------------------------------------------------------------

def render_404(data) -> None:
    body = (
        '<div class="nf">'
        '<p class="nf-code" aria-hidden="true">404</p>'
        "<h1>找不到這個頁面</h1>"
        '<p class="nf-lede">網址可能打錯了，或頁面已經搬移。可以從下面的入口繼續瀏覽，或直接搜尋。</p>'
        '<form class="nf-search" action="/search/" method="get" role="search">'
        '<label class="sr-only" for="nf-q">搜尋貼文</label>'
        '<input class="input" id="nf-q" name="q" type="search" placeholder="搜尋候選人、議題或關鍵字…">'
        f'<button class="btn btn-primary" type="submit">{S.icon("search")}搜尋</button></form>'
        '<div class="nf-links">'
        f'<a class="btn" href="/">{S.icon("home")}最新發文</a>'
        f'<a class="btn" href="/source/">{S.icon("people")}候選人</a>'
        f'<a class="btn" href="/search/">{S.icon("search")}搜尋頁</a>'
        "</div></div>"
    )
    html = S.layout("404", "找不到頁面", "找不到這個頁面。", "/404.html", body, extra_css=CSS, noindex=True)
    S.write_text("404.html", html)


def render(data) -> None:
    render_source_index(data)
    render_feeds(data)
    render_about(data)
    render_404(data)
