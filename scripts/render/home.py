"""`/` — story strip + six-city feed deck (DESIGN.md §7.1).

Also writes the client-side load-more bundles under site/data/feed/:
  <city>.json   newest 400 posts of that city
  all.json      newest 400 posts overall
  c/<id>.json   newest 400 posts of one candidate (single-candidate columns)
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from typing import Any, Dict, List

from . import shell as S

FEED_DIR = S.SITE_ROOT / "data" / "feed"
SSR_PER_COL = 30
BUNDLE_SIZE = 400
BADGE_WINDOW = dt.timedelta(hours=48)
BUNDLE_KEYS = ("id", "candidateId", "platform", "url", "postedAt", "text", "imageUrl", "imageAspect", "topics")


def safe_http(url: Any) -> str:
    """Only http(s) URLs may reach an href; anything else becomes ""."""
    u = str(url or "").strip()
    return u if u.lower().startswith(("http://", "https://")) else ""


def _slim(post: Dict[str, Any]) -> Dict[str, Any]:
    """Only the fields MO.postHTML reads."""
    out = {k: post.get(k) for k in BUNDLE_KEYS}
    out["url"] = safe_http(out.get("url"))
    intent = post.get("postingIntent")
    if isinstance(intent, dict) and intent.get("type"):
        out["postingIntent"] = {k: intent.get(k) for k in ("type", "label", "confidence", "reason")}
    return out


def _write_bundle(path, posts: List[Dict[str, Any]], generated: str, **meta: Any) -> None:
    payload = {"version": 1, "generatedAt": generated, **meta, "count": len(posts), "posts": [_slim(p) for p in posts]}
    S.write_text(path, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def write_bundles(data, by_city: Dict[str, List[Dict[str, Any]]]) -> None:
    shutil.rmtree(FEED_DIR, ignore_errors=True)
    generated = data.generated_at.isoformat()
    for city in S.CITY_ORDER:
        _write_bundle(FEED_DIR / f"{city}.json", by_city[city][:BUNDLE_SIZE], generated, city=city,
                      total=len(by_city[city]))
    _write_bundle(FEED_DIR / "all.json", data.all_posts()[:BUNDLE_SIZE], generated, city="all",
                  total=len(data.all_posts()))
    for c in data.candidates:
        posts = data.posts_for(c["id"])
        _write_bundle(FEED_DIR / "c" / f"{c['id']}.json", posts[:BUNDLE_SIZE], generated, candidate=c["id"],
                      total=len(posts))


# ---------------------------------------------------------------------------
# Story strip
# ---------------------------------------------------------------------------

def story_strip(data) -> str:
    ref = data.generated_at
    ordered = sorted(data.candidates, key=lambda c: S.epoch(c.get("latestPostAt")), reverse=True)
    items = []
    for c in ordered:
        recent = 0
        for p in data.posts_for(c["id"]):  # newest first
            stamp = S.parse_ts(p.get("postedAt"))
            if stamp is None:
                continue
            if ref - stamp > BADGE_WINDOW:
                break
            recent += 1
        badge = (f'<span class="story-badge" aria-hidden="true">{recent}</span>' if recent else "")
        src = S.asset_abs(c.get("avatarUrl"))
        img = (f'<img src="{S.esc(src)}" alt="" width="58" height="58" loading="lazy" decoding="async">' if src
               else f'<span class="avatar-initial" aria-hidden="true">{S.esc(c["name"][:1])}</span>')
        label = f'{c["name"]}（{S.city_label(c.get("city"))}）' + (f"，近 48 小時 {recent} 則" if recent else "")
        items.append(
            f'<a class="story-item" href="/?candidate={S.esc(c["id"])}" data-candidate="{S.esc(c["id"])}" '
            f'data-party="{S.party_slug(c.get("party"))}" aria-label="{S.esc(label)}" title="{S.esc(label)}">'
            f'<span class="story-ring">{img}{badge}</span><span class="story-name">{S.esc(c["name"])}</span></a>'
        )
    return f'<nav class="story-strip" aria-label="候選人（依最新發文排序，數字為近 48 小時貼文數）">{"".join(items)}</nav>'


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------

def column(key: str, title: str, posts_html: str, city: str = "", extra_cls: str = "", total: int = 0) -> str:
    """One deck column. Markup mirrors colShell() in pages/home.js."""
    uid = key.replace(":", "-")
    city_attr = f' data-city="{S.esc(city)}"' if city else ""
    cls = "feed-col" + (f" {extra_cls}" if extra_cls else "")
    more = ('<div class="feed-more"><button class="btn btn-sm" type="button" data-act="more">載入更多</button></div>'
            if total > SSR_PER_COL else "")
    return (
        f'<section class="{cls}" data-col="{S.esc(key)}"{city_attr} aria-labelledby="col-{uid}-t">'
        f'<header class="feed-col-head"><span class="feed-col-dot" aria-hidden="true"></span>'
        f'<h2 class="feed-col-title" id="col-{uid}-t">{S.esc(title)}</h2>'
        f'<span class="feed-col-count" aria-live="polite"></span>'
        f'<div class="feed-col-tools" hidden>'
        f'<button class="col-btn" type="button" data-act="filter" aria-expanded="false" aria-controls="col-{uid}-f">'
        f'{S.icon("filter")}<span class="col-btn-label">篩選</span></button>'
        f'<button class="col-btn" type="button" data-act="remove" aria-label="移除「{S.esc(title)}」欄">{S.icon("close")}</button>'
        f'</div></header>'
        f'<div class="col-filters" id="col-{uid}-f" hidden></div>'
        f'<div class="col-body" tabindex="-1">{posts_html}{more}</div></section>'
    )


def deck(data, by_city: Dict[str, List[Dict[str, Any]]]) -> str:
    ctx = data.post_ctx(show_city=False)
    cols = []
    for city in S.CITY_ORDER:
        posts = by_city[city]
        body = "".join(S.render_post(p, ctx) for p in posts[:SSR_PER_COL]) or S.render_empty(
            "這個城市尚無貼文", "候選人發文後會出現在這裡。")
        cols.append(column(f"city:{city}", S.city_label(city, False), body, city, total=len(posts)))
    # Phone default (全部): hidden ≥700px until the deck script decides otherwise.
    all_posts = data.all_posts()
    all_body = "".join(S.render_post(p, data) for p in all_posts[:SSR_PER_COL])
    cols.insert(0, column("all", "全部城市", all_body, extra_cls="is-active is-phone-only", total=len(all_posts)))
    add = (
        '<div class="deck-add" hidden>'
        f'<button class="feed-col-add" type="button" aria-expanded="false" aria-controls="addcol-menu">'
        f'{S.icon("plus")}<span>加欄</span></button>'
        '<div class="addcol-menu" id="addcol-menu" role="group" aria-label="加入欄位" hidden></div></div>'
    )
    return f'<div class="feed-cols" id="deck" aria-label="貼文河道">{"".join(cols)}{add}</div>'


def city_seg() -> str:
    btns = ['<button type="button" data-mcol="all" aria-pressed="true">全部</button>']
    btns += [f'<button type="button" data-mcol="city:{c}" aria-pressed="false">{S.city_label(c)}</button>'
             for c in S.CITY_ORDER]
    return f'<div class="seg deck-seg" role="group" aria-label="切換城市" hidden>{"".join(btns)}</div>'


def boot_json(data) -> str:
    cands = [{k: c.get(k) for k in ("id", "name", "city", "party", "avatarUrl")} for c in data.candidates]
    payload = {"candidates": cands, "topics": list(S.TOPIC_SLUGS), "cities": S.CITY_ORDER,
               "perCol": SSR_PER_COL, "bundle": BUNDLE_SIZE, "v": S.epoch(data.generated_at.isoformat())}
    raw = (json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
           .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
           .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return f'<script type="application/json" id="home-boot">{raw}</script>'


def render(data) -> None:
    by_city: Dict[str, List[Dict[str, Any]]] = {c: [] for c in S.CITY_ORDER}
    for p in data.all_posts():
        city = (data.by_id.get(p.get("candidateId")) or {}).get("city")
        if city in by_city:
            by_city[city].append(p)
    write_bundles(data, by_city)

    snap = S.fmt_time_tpe(data.generated_at.isoformat(), True)
    meta = (
        '<div class="deck-meta">'
        f'<p class="snapshot">資料快照 <time datetime="{S.esc(data.generated_at.isoformat())}">{S.esc(snap)}</time>（GMT+8）'
        '・非官方觀測站，貼文皆連回原文；議題與動機為 AI 分類，僅供參考。'
        '<a href="/about/">關於本站</a></p>'
        f'{city_seg()}</div>'
        '<div class="notice deck-banner" data-tone="info" hidden></div>'
    )
    body = (
        '<h1 class="sr-only">最新貼文：六都市長候選人官方帳號</h1>'
        + story_strip(data) + meta + deck(data, by_city) + boot_json(data)
        + '<noscript><p class="snapshot">啟用 JavaScript 後可篩選、增減欄位與載入更多貼文；'
          '也可以到<a href="/source/">候選人目錄</a>瀏覽每位候選人的完整貼文。</p></noscript>'
    )
    jsonld = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": S.SITE_NAME,
        "alternateName": S.SITE_SHORT,
        "url": S.BASE_URL + "/",
        "inLanguage": "zh-Hant",
        "description": S.DEFAULT_DESCRIPTION,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": S.BASE_URL + "/search/?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    }
    html = S.layout("home", f"{S.SITE_NAME}｜六都候選人最新發文", S.DEFAULT_DESCRIPTION, "/", body,
                    extra_css=["pages/home.css"], extra_js=["pages/home.js"], jsonld=jsonld,
                    body_class="layout-deck")
    S.write_page("/", html)
