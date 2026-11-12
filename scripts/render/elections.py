"""/elections/ — every 2026 local-election candidate (候選人名單與號次).

Reads the static API written by scripts/build_election_data.py:

  /elections/                               hub: totals by category, counties, search
  /elections/<county>/                      county: one card per race type
  /elections/<county>/<category>/           county-wide list (mayor, councils, township heads…)
  /elections/<county>/<category>/t<code>/   one township (鄉鎮市民代表、村里長)

Only the six-municipality mayor candidates have official-post timelines; every
other row says so explicitly (尚未追蹤社群貼文) instead of rendering an empty feed.
"""

from __future__ import annotations

import shutil
from typing import Any

from . import shell as S

API = S.SITE_ROOT / "api" / "elections" / "2026"
OUT = S.SITE_ROOT / "elections"
CSS = ["pages/elections.css"]
JS = ["pages/elections.js"]
UNTRACKED = "尚未追蹤社群貼文"


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


def _search_box(placeholder: str = "搜尋候選人姓名、選舉區或村里", scope: str = "") -> str:
    scope_attr = f' data-scope="{S.esc(scope)}"' if scope else ""
    return (
        f'<form class="el-search" role="search" action="/elections/" method="get"{scope_attr}>'
        f'<label class="sr-only" for="el-q">搜尋候選人</label>'
        f'{S.icon("search", "icon el-search-icon")}'
        f'<input class="input" id="el-q" name="q" type="search" autocomplete="off" placeholder="{S.esc(placeholder)}">'
        '</form>'
        '<div class="el-results" aria-live="polite" hidden></div>'
    )


def _source_line(generated: str) -> str:
    return (f'<p class="el-meta small muted">資料來源：中央選舉委員會與各直轄市、縣（市）選舉委員會公告；'
            f'本站整理時間 {S.esc(S.fmt_date_tpe(generated))}。'
            '<a href="/api/elections/2026/reconciliation.json">對帳報告</a>・'
            '<a href="/api/elections/2026/sources.json">來源清單</a>・'
            '<a href="/api/elections/2026/candidates.csv">CSV 下載</a></p>')


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
    if c.get("trackedFeed"):
        bits.append(f'<a class="ballot-feed" href="{S.esc(c["trackedFeed"])}">官方貼文河道</a>')
    else:
        bits.append(f'<span class="ballot-untracked">{UNTRACKED}</span>')
    if c["numberSource"] != district_source:
        bits.append(f'<a class="ballot-src" href="{S.esc(c["numberSource"])}" rel="noopener">號次來源</a>')
    inc = '<span class="ballot-inc">2022 當選</span>' if c.get("incumbent") else ""
    return (
        f'<li class="ballot-item" id="{anchor(c)}"><span class="ballot-no">{int(c["number"])}</span>'
        f'<span class="ballot-body"><span class="ballot-line"><b class="ballot-name">{S.esc(c["name"])}</b>'
        f'<span class="chip-soft chip-party" data-party="{S.party_slug(party)}">{S.esc(c.get("partyShort") or party)}</span>{inc}</span>'
        f'<span class="ballot-line ballot-sub">{"・".join(bits)}</span></span></li>'
    )


def _district(d: dict[str, Any], heading_level: int = 3) -> str:
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
    extra = "六都市長候選人另有官方貼文河道，點「官方貼文河道」前往。" if has_tracked else ""
    return (f'<div class="notice" data-tone="info"><p>本頁列出選委會公告的候選人、號次與推薦政黨。'
            f'本站目前只追蹤六都市長候選人的官方社群貼文，其他候選人標示「{UNTRACKED}」。{extra}'
            '「2022 當選」依中選會選舉資料庫比對同選舉同姓名推定，補選或解職異動可能未反映。</p></div>')


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
            return (f'<div class="card county-card is-pending"><p class="card-title">{S.esc(c["label"])}</p>'
                    '<p class="card-meta">號次公告整理中</p></div>')
        return (f'<a class="card county-card" href="{S.esc(c["path"])}"><p class="card-title">{S.esc(c["label"])}</p>'
                f'<p class="card-meta">{c["count"]:,} 位候選人・{len(c["categories"])} 類選舉</p></a>')

    rec = index["reconciliation"]
    rec_note = ""
    if rec.get("unexplained") or rec.get("pendingSource"):
        rec_note = (f'<div class="notice" data-tone="warn"><p>對帳中：{rec.get("pendingSource", 0):,} 位登記者的號次公告尚未取得、'
                    f'{rec.get("unexplained", 0):,} 筆差異待確認。詳見 <a href="/api/elections/2026/reconciliation.json">對帳報告</a>。</p></div>')
    body = (
        S.page_head("2026 地方選舉候選人", "11 月 28 日投票的九合一地方選舉：直轄市長、縣市長、議員、鄉鎮市長、代表與村里長，"
                    f"共 <b>{index['count']:,}</b> 位候選人。依縣市、選舉類別與選舉區瀏覽，或直接搜尋。", eyebrow="候選人名單與號次")
        + _search_box()
        + f'<div class="grid-4 el-tiles">{tiles}</div>'
        + rec_note
        + f'<section class="section"><h2 class="section-title">直轄市</h2><div class="grid-4">{"".join(card(c) for c in muni)}</div></section>'
        + f'<section class="section"><h2 class="section-title">縣（市）</h2><div class="grid-4">{"".join(card(c) for c in other)}</div></section>'
        + _notice_untracked(True)
        + _source_line(gen)
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
        inc = f"・2022 當選 {cat['incumbents']} 人" if cat.get("incumbents") else ""
        cards.append(f'<a class="card" href="{S.esc(cat["path"])}"><p class="card-title">{S.esc(cat["label"])}</p>'
                     f'<p class="card-meta">{sub}{cat["count"]:,} 位候選人{inc}</p></a>')
    body = (
        _crumbs(crumbs)
        + S.page_head(f"{c['label']} 2026 候選人", f"{c['label']}共 <b>{county['count']:,}</b> 位候選人。選擇選舉類別查看各選舉區號次。",
                      actions_html=f'<a class="btn btn-ghost btn-sm" href="/api/elections/2026/{S.esc(c["id"])}.json">{S.icon("json")}<span>JSON</span></a>')
        + _search_box(f"搜尋{c['label']}候選人、選舉區或村里", c["id"])
        + f'<div class="grid-3 el-cats">{"".join(cards)}</div>'
        + _notice_untracked(c["municipality"])
        + f'<p class="el-meta small muted">號次公告：<a href="{S.esc(c["commission"])}" target="_blank" rel="noopener">{S.esc(c["label"])}選舉委員會</a>'
        f'・取得時間 {S.esc(S.fmt_date_tpe(county.get("numbersFetchedAt")))}</p>'
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
    crumbs = [("候選人名單", "/elections/"), (c["label"], f"/elections/{c['id']}/"), (cat["label"], None)]
    title = f"{c['label']}{cat['label']}候選人"
    towns = [g for g in cat["groups"] if g["key"]]
    head = S.page_head(title, f"共 <b>{cat['count']:,}</b> 位候選人，依選舉區列出號次。")
    pages = 0
    if towns:
        chips = "".join(
            f'<a class="card town-card" href="{S.esc(g["path"])}"><p class="card-title">{S.esc(g["label"])}</p>'
            f'<p class="card-meta">{len(g["districts"])} 個選舉區・{sum(len(d["candidates"]) for d in g["districts"])} 人</p></a>'
            for g in towns
        )
        body = (_crumbs(crumbs) + head + _search_box(f"搜尋{c['label']}候選人或村里", c["id"])
                + f'<div class="grid-4 el-towns">{chips}</div>' + _notice_untracked(False))
        for g in towns:
            render_town(county, cat, g)
            pages += 1
    else:
        districts = [d for g in cat["groups"] for d in g["districts"]]
        jump = ""
        if len(districts) > 6:
            jump = '<nav class="el-jump" aria-label="選舉區">' + "".join(
                f'<a class="chip" href="#d-{S.esc(d["key"])}">{S.esc(d["label"] if not d["township"] else d["township"] + (d["label"] if d["label"] != d["township"] else ""))}</a>'
                for d in districts) + "</nav>"
        blocks = "".join(_district({**d, "label": (d["township"] + d["label"]) if d["township"] and d["label"] != d["township"] else d["label"]}) for d in districts)
        has_tracked = any(x.get("trackedFeed") for d in districts for x in d["candidates"])
        body = _crumbs(crumbs) + head + jump + _notice_untracked(has_tracked) + f'<div class="districts">{blocks}</div>'
    body += _source_line(county.get("generatedAt"))
    S.write_page(path, S.layout("elections", title, f"{title}名單：號次、推薦政黨、選舉區與選委會公告來源。",
                                path, body, extra_css=CSS, extra_js=JS, jsonld=_breadcrumb_ld(crumbs, path)))
    return pages + 1


def render_town(county: dict[str, Any], cat: dict[str, Any], group: dict[str, Any]) -> None:
    c = county["county"]
    path = group["path"]
    crumbs = [("候選人名單", "/elections/"), (c["label"], f"/elections/{c['id']}/"), (cat["label"], cat["path"]), (group["label"], None)]
    title = f"{c['label']}{group['label']}{cat['label']}候選人"
    n = sum(len(d["candidates"]) for d in group["districts"])
    grid = " districts-grid" if cat["id"] == "village-chief" else ""
    blocks = "".join(_district(d) for d in group["districts"])
    unit = "村里" if cat["id"] == "village-chief" else "選舉區"
    body = (_crumbs(crumbs) + S.page_head(title, f"{len(group['districts'])} 個{unit}、<b>{n:,}</b> 位候選人。")
            + _notice_untracked(False) + f'<div class="districts{grid}">{blocks}</div>' + _source_line(county.get("generatedAt")))
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
