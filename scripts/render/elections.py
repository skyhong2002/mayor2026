"""/elections/ — every 2026 local-election candidate (候選人名單與號次).

Reads the static API written by scripts/build_election_data.py:

  /elections/                               hub: totals by category, counties, search
  /elections/<county>/                      county: one card per race type
  /elections/<county>/<category>/           county-wide list (mayor, councils, township heads…)
  /elections/<county>/<category>/t<code>/   one township (鄉鎮市民代表、村里長)

Official-post links appear where tracked; all other candidates retain their
complete ballot records and announcement sources.
"""

from __future__ import annotations

import shutil
from typing import Any

from . import shell as S

API = S.SITE_ROOT / "api" / "elections" / "2026"
OUT = S.SITE_ROOT / "elections"
CSS = ["pages/elections.css"]
JS = ["pages/elections.js"]


def _category_label(cat: dict[str, Any]) -> str:
    return {"municipal-mayor": "市長", "municipal-councilor": "市議員", "village-chief": "村里長"}.get(cat["id"], cat["label"])


def _crumbs(items: list[tuple[str, str | None]]) -> str:
    parts = []
    for label, href in items:
        parts.append(f'<a href="{S.esc(href)}">{S.esc(label)}</a>' if href else f'<span aria-current="page">{S.esc(label)}</span>')
    sep = '<span aria-hidden="true">›</span>'
    return f'<nav class="crumbs" aria-label="階層導覽">{sep.join(parts)}</nav>'


def _breadcrumb_ld(items: list[tuple[str, str | None]], here: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label, "item": S.canonical(href or here)}
            for i, (label, href) in enumerate(items)
        ],
    }


def _search_box(placeholder: str = "姓名、選舉區或村里", scope: str = "", category: str = "", *, local: bool = False, index: dict | None = None, districts: list | None = None) -> str:
    attrs = f' data-scope="{S.esc(scope)}" data-category="{S.esc(category)}"' + (' data-local="true"' if local else '')
    filters = ""
    if index:
        counties = "".join(f'<option value="{S.esc(c["id"])}">{S.esc(c["label"])}</option>' for c in index["counties"] if c["count"])
        categories = "".join(f'<option value="{S.esc(c["id"])}">{S.esc(_category_label(c))}</option>' for c in index["categories"])
        filters = (f'<div class="el-search-filters"><label>縣市<select name="county"><option value="">全部縣市</option>{counties}</select></label>'
                   f'<label>職位<select name="category"><option value="">全部職位</option>{categories}</select></label></div>')
    jump = ""
    if districts and len(districts) > 6:
        options = "".join(f'<option value="d-{S.esc(d["key"])}">{S.esc((d["township"] + d["label"]) if d.get("township") and d["township"] != d["label"] else d["label"])}</option>' for d in districts)
        jump = f'<label class="el-jump-select" for="el-district">或直接跳到選區<select id="el-district"><option value="">選擇村里／選舉區</option>{options}</select></label>'
    return (
        f'<section class="el-finder" aria-label="查找候選人"><form class="el-search" role="search" action="" method="get"{attrs}>'
        f'<label class="el-search-label" for="el-q">{"在這份名單中搜尋" if local else "搜尋候選人"}</label>'
        f'<div class="el-search-field">{S.icon("search", "icon el-search-icon")}'
        f'<input class="input" id="el-q" name="q" type="search" autocomplete="off" placeholder="{S.esc(placeholder)}">'
        '<button class="el-clear" type="button" hidden aria-label="清除搜尋與篩選">清除</button></div>' + filters +
        '</form>' + jump + '<p class="el-search-status" role="status" aria-live="polite" hidden></p>'
        '<div class="el-results" hidden></div><noscript><p>搜尋需啟用 JavaScript；下方仍可依縣市與職位瀏覽完整名單。</p></noscript></section>'
    )


def _source_line(generated: str) -> str:
    return (f'<p class="el-meta small muted">資料來源：中央選舉委員會與各直轄市、縣（市）選舉委員會公告；'
            f'本站整理時間 {S.esc(S.fmt_date_tpe(generated))}。'
            '<a href="/api/elections/2026/reconciliation.json">對帳報告</a>・'
            '<a href="/api/elections/2026/sources.json">來源清單</a>・'
            '<a href="/api/elections/2026/candidates.csv">CSV 下載</a></p>')


def _freshness(generated: str) -> str:
    return (f'<p class="el-freshness">選委會公告 · 整理於 {S.esc(S.fmt_date_tpe(generated))}'
            ' · <a href="/api/elections/2026/sources.json">查看來源</a></p>')


def anchor(c: dict[str, Any]) -> str:
    """In-page anchor of a candidate row (unique within its county+category page)."""
    return f"{c['districtKey']}-{int(c['number'])}"


def _candidate(c: dict[str, Any], district_source: str) -> str:
    party = c.get("party") or "無"
    bits = []
    if c.get("gender"):
        bits.append(S.esc(c["gender"]))
    if c.get("birthYear"):
        bits.append(f"{int(c['birthYear'])} 年生")
    feed = (f'<a class="ballot-feed" href="{S.esc(c["trackedFeed"])}">官方貼文 →</a>' if c.get("trackedFeed") else "")
    if c["numberSource"] != district_source:
        bits.append(f'<a class="ballot-src" href="{S.esc(c["numberSource"])}" rel="noopener">號次來源</a>')
    sub = f'<span class="ballot-line ballot-sub">{"・".join(bits)}</span>' if bits else ""
    inc = '<span class="ballot-inc" title="依 2022 中選會同選舉、同姓名資料比對">2022 當選</span>' if c.get("incumbent") else ""
    return (
        f'<li class="ballot-item" id="{anchor(c)}"><span class="ballot-no" aria-label="號次 {int(c["number"])}">{int(c["number"])}</span>'
        f'<span class="ballot-body"><span class="ballot-line"><b class="ballot-name">{S.esc(c["name"])}</b>'
        f'<span class="chip-soft chip-party" data-party="{S.party_slug(party)}">{S.esc(c.get("partyShort") or party)}</span>{inc}</span>'
        f'{sub}</span>{feed}</li>'
    )


def _district(d: dict[str, Any], heading_level: int = 2) -> str:
    seats = f'應選 {d["seats"]} 名・' if d.get("seats") else ""
    h = f"h{heading_level}"
    sources = [c["numberSource"] for c in d["candidates"]]
    src = max(set(sources), key=sources.count)
    return (
        f'<section class="district" id="d-{S.esc(d["key"])}">'
        f'<header class="district-head"><{h} class="district-title">{S.esc(d["label"])}</{h}>'
        f'<span class="district-count">{seats}候選 {len(d["candidates"])} 人・'
        f'<a href="{S.esc(src)}" rel="noopener">號次來源</a></span></header>'
        f'<ol class="ballot">{"".join(_candidate(c, src) for c in d["candidates"])}</ol></section>'
    )


def _notice_untracked(has_tracked: bool) -> str:
    return ('<details class="el-note"><summary>名單與資料說明</summary><p>號次與推薦政黨依選委會公告整理。'
            '「官方貼文」連至已追蹤的社群資料，其他候選人目前僅提供公告名單。'
            '「2022 當選」依中選會同選舉、同姓名比對，補選或解職異動可能未反映。</p></details>')


def _compare_link(county: str, category: str = "", *, compact: bool = False) -> str:
    if county != "taipei" or category not in ("", "municipal-mayor"):
        return ""
    if compact:
        return '<p class="el-compare-inline"><a href="/compare/taipei/">前往臺北市長政見比較 →</a></p>'
    return ('<a class="el-compare" href="/compare/taipei/"><span><strong>臺北市長政見比較</strong>'
            '<span>把候選人的主張放在一起看</span></span><span aria-hidden="true">→</span></a>')


def render_hub(index: dict[str, Any]) -> None:
    gen = index.get("generatedAt")
    tiles = "".join(
        f'<div class="stat-tile"><span class="stat-value">{c["count"]:,}</span><span class="stat-label">{S.esc(c["label"])}</span>'
        f'<span class="stat-hint">應選 {c["official"].get("officialSeats") or "—"} 名</span></div>'
        for c in index["categories"]
    )
    muni = [c for c in index["counties"] if c["municipality"]]
    other = [c for c in index["counties"] if not c["municipality"]]

    def card(c: dict[str, Any]) -> str:
        if not c["count"]:
            return (f'<div class="card county-card is-pending" aria-label="{S.esc(c["label"])}，公告整理中"><p class="card-title">{S.esc(c["label"])}</p>'
                    '<p class="card-meta">號次公告整理中</p></div>')
        return (f'<a class="card county-card" href="{S.esc(c["path"])}"><p class="card-title">{S.esc(c["label"])}</p>'
                f'<p class="card-meta">已收錄 {c["count"]:,} 人 · {len(c["categories"])} 職位</p></a>')

    rec = index["reconciliation"]
    rec_note = ""
    if rec.get("unexplained") or rec.get("pendingSource"):
        rec_note = (f'<div class="notice" data-tone="warn"><p>對帳中：{rec.get("pendingSource", 0):,} 位登記者的號次公告尚未取得、'
                    f'{rec.get("unexplained", 0):,} 筆差異待確認。詳見 <a href="/api/elections/2026/reconciliation.json">對帳報告</a>。</p></div>')
    body = (
        '<header class="el-hero"><p class="eyebrow">候選人名單 · 11 月 28 日投票</p>'
        '<h1>找到你的候選人。</h1>'
        f'<p>搜尋姓名，或依縣市查名單與號次。<span class="el-total">已取得號次公告 {index["count"]:,} 位</span></p></header>'
        + _freshness(gen)
        + ('<details class="el-coverage"><summary>收錄範圍：部分號次公告待補</summary>' + rec_note + '</details>' if rec_note else '')
        + _search_box(index=index)
        + '<div data-el-browse>'
        + '<section class="el-counties" aria-labelledby="el-counties-title"><div class="el-section-heading"><h2 id="el-counties-title">依縣市瀏覽</h2><span>選縣市，再選職位</span></div>'
        + f'<h3 class="el-group-title">直轄市</h3><div class="el-county-grid">{"".join(card(c) for c in muni)}</div>'
        + f'<h3 class="el-group-title">縣（市）</h3><div class="el-county-grid">{"".join(card(c) for c in other)}</div></section>'
        + _compare_link("taipei")
        + '<details class="el-statistics"><summary>各類選舉收錄概況</summary>'
        + f'<div class="el-stats-grid">{tiles}</div></details></div>'
        + _notice_untracked(True) + _source_line(gen)
    )
    items = [("候選人名單", None)]
    html = S.layout("elections", "2026 地方選舉候選人名單與號次",
                    f"2026 年 11 月 28 日地方選舉全部 {index['count']:,} 位候選人：依縣市、選舉類別、選舉區與村里查詢號次、推薦政黨與官方公告來源。",
                    "/elections/", body, extra_css=CSS, extra_js=JS, jsonld=_breadcrumb_ld(items, "/elections/"))
    S.write_page("/elections/", html)


def render_county(county: dict[str, Any]) -> int:
    c = county["county"]
    path = f"/elections/{c['id']}/"
    crumbs = [("候選人名單", "/elections/"), (c["label"], None)]
    cards = []
    for cat in county["categories"]:
        towns = [g for g in cat["groups"] if g["key"]]
        sub = f"{len(towns)} 個鄉鎮市區・" if towns else ""
        cards.append(f'<a class="card" href="{S.esc(cat["path"])}"><p class="card-title">{S.esc(_category_label(cat))}</p>'
                     f'<p class="card-meta">{sub}{cat["count"]:,} 位候選人</p></a>')
    body = (
        _crumbs(crumbs)
        + S.page_head(f"{c['label']}候選人", f"已取得號次公告 <b>{county['count']:,}</b> 位。選擇職位，查看名單。")
        + _freshness(county.get("generatedAt")) + _search_box(f"姓名、選舉區或村里", c["id"])
        + '<div data-el-browse><h2 class="el-section-title">選擇職位</h2>' + f'<div class="grid-3 el-cats">{"".join(cards)}</div>' + _compare_link(c['id']) + '</div>'
        + _notice_untracked(c["municipality"])
        + f'<p class="el-meta small muted">號次公告：<a href="{S.esc(c["commission"])}" target="_blank" rel="noopener">{S.esc(c["label"])}選舉委員會</a>'
        f'・取得時間 {S.esc(S.fmt_date_tpe(county.get("numbersFetchedAt")))} · <a href="/api/elections/2026/{S.esc(c["id"])}.json">JSON 下載</a></p>'
    )
    S.write_page(path, S.layout("elections", f"{c['label']} 2026 地方選舉候選人",
                                f"{c['label']} 2026 地方選舉 {county['count']:,} 位候選人的號次、推薦政黨與選委會公告來源。",
                                path, body, extra_css=CSS, extra_js=JS, jsonld=_breadcrumb_ld(crumbs, path)))
    pages = 1
    for cat in county["categories"]:
        pages += render_category(county, cat)
    return pages


def render_category(county: dict[str, Any], cat: dict[str, Any]) -> int:
    c = county["county"]
    path = cat["path"]
    crumbs = [("候選人名單", "/elections/"), (c["label"], f"/elections/{c['id']}/"), (_category_label(cat), None)]
    title = f"{c['label']}{_category_label(cat)}候選人"
    towns = [g for g in cat["groups"] if g["key"]]
    head = S.page_head(title, f"共 <b>{cat['count']:,}</b> 位候選人，依選舉區列出號次。") + _freshness(county.get("generatedAt"))
    pages = 0
    if towns:
        chips = "".join(
            f'<a class="card town-card" href="{S.esc(g["path"])}"><p class="card-title">{S.esc(g["label"])}</p>'
            f'<p class="card-meta">{len(g["districts"])} 個選舉區・{sum(len(d["candidates"]) for d in g["districts"])} 人</p></a>'
            for g in towns
        )
        body = (_crumbs(crumbs) + head + _search_box(f"姓名、行政區或村里", c["id"], cat["id"])
                + f'<div class="grid-4 el-towns" data-el-browse>{chips}</div>' + _notice_untracked(False))
        for g in towns:
            render_town(county, cat, g)
            pages += 1
    else:
        districts = [d for g in cat["groups"] for d in g["districts"]]
        blocks = "".join(_district({**d, "label": (d["township"] + d["label"]) if d["township"] and d["label"] != d["township"] else d["label"]}) for d in districts)
        has_tracked = any(x.get("trackedFeed") for d in districts for x in d["candidates"])
        body = (_crumbs(crumbs) + head
                + _search_box("姓名、政黨或選舉區", c["id"], cat["id"], local=True, districts=districts)
                + _compare_link(c["id"], cat["id"], compact=True) + f'<div class="districts">{blocks}</div>' + _notice_untracked(has_tracked))
    body += _source_line(county.get("generatedAt"))
    S.write_page(path, S.layout("elections", title, f"{title}名單：號次、推薦政黨、選舉區與選委會公告來源。",
                                path, body, extra_css=CSS, extra_js=JS, jsonld=_breadcrumb_ld(crumbs, path)))
    return pages + 1


def render_town(county: dict[str, Any], cat: dict[str, Any], group: dict[str, Any]) -> None:
    c = county["county"]
    path = group["path"]
    crumbs = [("候選人名單", "/elections/"), (c["label"], f"/elections/{c['id']}/"), (_category_label(cat), cat["path"]), (group["label"], None)]
    display_title = f"{group['label']}{'里長' if cat['id'] == 'village-chief' and c['municipality'] else cat['label']}候選人"
    title = f"{c['label']}{display_title}"
    n = sum(len(d["candidates"]) for d in group["districts"])
    grid = " districts-grid" if cat["id"] == "village-chief" else ""
    blocks = "".join(_district(d) for d in group["districts"])
    unit = "村里" if cat["id"] == "village-chief" else "選舉區"
    body = (_crumbs(crumbs) + S.page_head(display_title, f"{len(group['districts'])} 個{unit}、<b>{n:,}</b> 位候選人。")
            + _freshness(county.get("generatedAt")) + _search_box("姓名、政黨或村里", c["id"], cat["id"], local=True, districts=group["districts"])
            + f'<div class="districts{grid}">{blocks}</div>' + _notice_untracked(False) + _source_line(county.get("generatedAt")))
    S.write_page(path, S.layout("elections", title, f"{title}：各{unit}號次、推薦政黨與選委會公告來源。",
                                path, body, extra_css=CSS, extra_js=JS, jsonld=_breadcrumb_ld(crumbs, path)))


def render(data: Any = None) -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    index = S.read_json(API / "index.json", None)
    if not index:
        return
    render_hub(index)
    pages = 1
    for entry in index["counties"]:
        if not entry["count"]:
            continue
        county = S.read_json(API / f"{entry['id']}.json", None)
        if county:
            county.setdefault("generatedAt", index.get("generatedAt"))
            pages += render_county(county)
    print(f"elections: {pages} page(s)")
