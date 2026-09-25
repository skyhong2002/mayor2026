"""Candidate pages: /<city>/<id>/ (profile + timeline) and /source/<id>/
(watchlist account detail). Also writes the paged timeline data used by
assets/pages/candidate.js under site/data/candidate/<id>/.

Owns (and cleans before writing): site/<city>/ for the six cities,
site/source/<id>/ sub-directories (never site/source/index.html) and
site/data/candidate/.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
import shutil
from collections import Counter
from typing import Any

from . import shell as S

SSR_POSTS = 40
PAGE_SIZE = 60
ACTIVITY_DAYS = 30
MAX_KEYWORDS = 6
DATA_DIR = S.SITE_ROOT / "data" / "candidate"
WATCHLIST_CSV = S.PROJECT_ROOT / "data" / "sources" / "watchlist_accounts.csv"
WEEKDAYS = "一二三四五六日"

ROLE_LABELS = {
    "campaign": "競選", "personal": "個人", "incumbent": "現任職務",
    "party": "政黨", "affiliated": "關聯",
}
VERIFICATION_LABELS = {"first_party": "第一方", "cross_ref": "交叉比對", "unverified": "未驗證"}
VERIFICATION_HINTS = {
    "first_party": "由候選人官網或官方頁面直接連結確認",
    "cross_ref": "由多個公開來源交叉比對確認",
    "unverified": "尚未取得足夠佐證，僅供參考",
}
# status.json sources[].status → (badge state, label)
STATUS_BADGES = {
    "scheduled": ("ok", "正常"),
    "due": ("pending", "待執行"),
    "overdue": ("warn", "執行逾期"),
    "error": ("error", "抓取失敗"),
    "blocked": ("paused", "冷卻／額度限制"),
    "disabled": ("paused", "已停用"),
    "link_only": ("paused", "僅提供連結"),
}
ROLE_RANK = {"campaign": 0, "incumbent": 0, "personal": 1, "affiliated": 2, "party": 3}
VERIF_RANK = {"first_party": 0, "cross_ref": 1, "unverified": 2}
PLATFORM_ORDER = ["website", "facebook", "instagram", "threads", "youtube", "x", "podcast",
                  "line_oa", "line_openchat", "tiktok"]
SLIM_KEYS = ("id", "candidateId", "platform", "url", "postedAt", "text", "imageUrl", "imageAspect", "topics")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _party_label(c: dict[str, Any]) -> str:
    return (c.get("party") or "").strip() or "無黨籍"


def _account_label(acct: dict[str, Any]) -> str:
    platform = acct.get("platform") or "website"
    handle = (acct.get("handle") or "").strip()
    if not handle or handle.lower() == "unknown":
        return acct.get("displayName") or S.PLATFORM_LABELS.get(platform, platform)
    if platform in ("instagram", "threads", "x") and not handle.startswith("@"):
        return "@" + handle
    return handle


def _account_sort_key(acct: dict[str, Any]) -> tuple:
    platform = acct.get("platform") or ""
    return (
        0 if acct.get("active", True) else 1,
        PLATFORM_ORDER.index(platform) if platform in PLATFORM_ORDER else 99,
        ROLE_RANK.get(acct.get("role") or "", 9),
        VERIF_RANK.get(acct.get("verification") or "", 9),
    )


def _pct(n: int, d: int) -> str:
    return f"{round(100 * n / d)}%" if d else "—"


def _time_html(iso: Any, rel: bool = False) -> str:
    """<time> with absolute GMT+8 text; ``rel`` lets shell.js swap in relative time."""
    parsed = S.parse_ts(iso)
    if not parsed:
        return '<span class="muted">—</span>'
    attr = " data-rel" if rel else ""
    return (f'<time datetime="{S.esc(parsed.isoformat())}"{attr} title="{S.esc(S.fmt_time_tpe(iso, True))}">'
            f"{S.esc(S.fmt_time_tpe(iso))}</time>")


def _slim(post: dict[str, Any]) -> dict[str, Any]:
    out = {k: post.get(k) for k in SLIM_KEYS if post.get(k) is not None}
    intent = post.get("postingIntent")
    if isinstance(intent, dict) and intent.get("type"):
        out["postingIntent"] = {k: intent.get(k) for k in ("type", "label", "confidence", "reason")
                                if intent.get(k) is not None}
    return out


def _intent_type(post: dict[str, Any]) -> str:
    intent = post.get("postingIntent")
    return (intent.get("type") if isinstance(intent, dict) else intent) or ""


def _watchlist_rows() -> dict[str, dict[str, str]]:
    """watchlist_accounts.csv rows by account id (read-only; used for inactive accounts)."""
    if not WATCHLIST_CSV.is_file():
        return {}
    try:
        with WATCHLIST_CSV.open(encoding="utf-8", newline="") as fh:
            return {r["account_id"]: r for r in csv.DictReader(fh) if r.get("account_id")}
    except (OSError, KeyError, csv.Error):
        return {}


def _accounts(data, cid: str, status_by_id: dict[str, dict[str, Any]],
              csv_rows: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    """Active accounts from sources.json plus inactive ones known to status.json / CSV."""
    src = data.sources_by_id.get(cid) or {}
    out = [dict(a, active=True) for a in src.get("accounts") or []]
    seen = {a.get("id") for a in out}
    extra_ids = [s["id"] for s in status_by_id.values() if s.get("candidateId") == cid]
    extra_ids += [r["account_id"] for r in csv_rows.values() if r.get("candidate_id") == cid]
    for aid in extra_ids:
        if aid in seen:
            continue
        seen.add(aid)
        st = status_by_id.get(aid) or {}
        row = csv_rows.get(aid) or {}
        active = st.get("active")
        if active is None:
            active = (row.get("active") or "").strip().lower() == "true"
        out.append({
            "id": aid,
            "platform": st.get("platform") or row.get("platform") or "website",
            "url": st.get("url") or row.get("url"),
            "handle": row.get("handle") or "",
            "role": row.get("account_role") or "",
            "verification": row.get("verification") or "",
            "displayName": None,
            "avatarUrl": None,
            "active": bool(active),
        })
    for a in out:
        row = csv_rows.get(a.get("id")) or {}
        st = status_by_id.get(a.get("id")) or {}
        a["evidence"] = st.get("evidence") or row.get("evidence") or ""
    return sorted(out, key=_account_sort_key)


# ---------------------------------------------------------------------------
# shared header
# ---------------------------------------------------------------------------

def _profile_head(c: dict[str, Any], accounts: list[dict[str, Any]], post_counts: Counter,
                  compact: bool, actions_html: str, eyebrow: str) -> str:
    cid, city = c["id"], c.get("city") or ""
    home = f"/{city}/{cid}/"
    avatar = S.render_avatar(c, "md" if compact else "lg", href=home if compact else None,
                             cls="cand-avatar", label=c["name"])
    name = (f'<a href="{S.esc(home)}">{S.esc(c["name"])}</a>' if compact else S.esc(c["name"]))
    chips = [
        S.render_chip(_party_label(c), party=c.get("party") or "", soft=True),
        S.render_chip(S.city_label(city, False), href=f"/?city={city}", city=city, soft=True),
    ]
    acct_chips = []
    if not compact:
        for a in accounts:
            if not a.get("active", True) or not a.get("url"):
                continue
            platform = a.get("platform") or "website"
            plat_label = S.PLATFORM_LABELS.get(platform, platform)
            count = post_counts.get(a.get("id"), 0)
            acct_chips.append(S.render_chip(
                _account_label(a), href=a["url"], icon_name=platform, count=count or None, cls="cand-acct",
                attrs={"target": "_blank", "rel": "noopener", "title": f"{plat_label}・{ROLE_LABELS.get(a.get('role') or '', '')}帳號（開啟原站）",
                       "aria-label": f"{plat_label} {_account_label(a)}，已收錄 {count} 則（開啟原站）"},
            ))
    accts = (f'<div class="cand-accts" aria-label="監看帳號">{"".join(acct_chips)}</div>' if acct_chips else "")
    eb = f'<p class="page-eyebrow">{S.esc(eyebrow)}</p>' if eyebrow else ""
    return (
        f'<header class="cand-hero{" is-compact" if compact else ""}" data-party="{S.party_slug(c.get("party"))}">'
        f"{avatar}"
        f'<div class="cand-hero-main">{eb}<h1 class="cand-name">{name}</h1>'
        f'<div class="cand-chips">{"".join(chips)}</div>{accts}'
        f'<div class="cand-actions">{actions_html}</div></div></header>'
    )


# ---------------------------------------------------------------------------
# /<city>/<id>/
# ---------------------------------------------------------------------------

def _stat_tiles(posts: list[dict[str, Any]], latest_iso: Any, now: dt.datetime) -> str:
    total = len(posts)
    week_ago = now - dt.timedelta(days=7)
    two_weeks = now - dt.timedelta(days=14)
    recent = prev = 0
    for p in posts:
        ts = S.parse_ts(p.get("postedAt"))
        if not ts:
            continue
        if ts > week_ago:
            recent += 1
        elif ts > two_weeks:
            prev += 1
    intents = Counter(_intent_type(p) for p in posts)
    self_n, resp_n = intents.get("self_initiated", 0), intents.get("responsive", 0)
    classified = self_n + resp_n
    latest = (f'<span class="stat-value">{S.esc(S.fmt_time_tpe(latest_iso))}</span>'
              f'<span class="stat-hint"><time datetime="{S.esc(S.parse_ts(latest_iso).isoformat())}" data-rel>'
              f'{S.esc(S.rel_time_tpe(latest_iso, now))}</time>・GMT+8</span>'
              if S.parse_ts(latest_iso) else '<span class="stat-value">—</span><span class="stat-hint">尚無資料</span>')
    tiles = [
        (f"{total:,}", "已收錄貼文", "僅含 AI 已分類的公開貼文"),
        (f"{recent:,}", "近 7 天", f"前 7 天 {prev:,} 則"),
        (_pct(self_n, classified), "主動發文比", f"{self_n:,} 則"),
        (_pct(resp_n, classified), "回應他方觀點比", f"{resp_n:,} 則"),
    ]
    html = "".join(
        f'<div class="stat-tile"><span class="stat-value">{v}</span><span class="stat-label">{l}</span>'
        f'<span class="stat-hint">{S.esc(h)}</span></div>' for v, l, h in tiles
    )
    html += f'<div class="stat-tile"><span class="stat-label">最新發文</span>{latest}</div>'
    return f'<section class="cand-stats" aria-label="概覽">{html}</section>'


def _topics_card(data, cid: str) -> str:
    spec = next((r for r in data.spectrum if r.get("candidateId") == cid), None) or {}
    props = sorted(((t, v) for t, v in (spec.get("topicProportions") or {}).items() if t != "生活" and v > 0),
                   key=lambda kv: -kv[1])
    details = (data.topic_details or {}).get("topics") or {}
    if not props:
        inner = S.render_empty("尚無資料", "此候選人目前沒有足夠的已分類貼文可計算議題比例。")
    else:
        top = props[0][1]
        rows = []
        for topic, value in props:
            slug = S.topic_slug(topic)
            kws = [kw for kw in (details.get(topic) or {}).get(cid) or [] if kw and kw[0]][:MAX_KEYWORDS]
            kw_html = "".join(
                f'<span class="cand-kw">{S.esc(k)}<span class="cand-kw-n">×{int(n)}</span></span>' for k, n in kws
            )
            rows.append(
                f'<li class="cand-topic"><div class="meter-row">'
                f'<a class="meter-label" href="/spectrum/{slug}/">{S.esc(topic)}</a>'
                f'<div class="meter" role="img" aria-label="{S.esc(topic)} {value:.0%}">'
                f'<span class="meter-fill" style="--v:{value / top:.4f}"></span></div>'
                f'<span class="meter-value">{value:.0%}</span></div>'
                + (f'<div class="cand-kws" aria-label="{S.esc(topic)} 關鍵字">{kw_html}</div>' if kw_html else "")
                + "</li>"
            )
        inner = f'<ol class="cand-topics">{"".join(rows)}</ol>'
    return (
        '<section class="card cand-card" aria-labelledby="cand-topics-h">'
        '<div class="section-head"><h2 id="cand-topics-h">議題比例</h2>'
        '<a class="link-more" href="/spectrum/">議題光譜 →</a></div>'
        '<p class="cand-note">各議題占已分類貼文的比例（不含「生活」），條長以最高議題為滿格；'
        '關鍵字為該議題貼文中的命中次數。</p>'
        f"{inner}</section>"
    )


def _activity_card(posts: list[dict[str, Any]], now: dt.datetime) -> str:
    today = now.astimezone(S.TPE).date()
    days = [today - dt.timedelta(days=i) for i in range(ACTIVITY_DAYS - 1, -1, -1)]
    counts: Counter = Counter()
    for p in posts:
        ts = S.parse_ts(p.get("postedAt"))
        if ts:
            counts[ts.astimezone(S.TPE).date()] += 1
    values = [counts.get(d, 0) for d in days]
    total, peak = sum(values), max(values) if values else 0
    active_days = sum(1 for v in values if v)
    scale = max(peak, 1)
    bars = []
    for d, v in zip(days, values):
        label = f"{d.month}/{d.day}（{WEEKDAYS[d.weekday()]}）"
        bars.append(
            f'<li class="act-day{" is-zero" if not v else ""}" style="--v:{v / scale:.4f}" data-label="{label}" data-n="{v}" '
            f'title="{label}・{v} 則"><span class="act-bar"></span><span class="sr-only">{label} {v} 則</span></li>'
        )
    ticks = [days[0], days[len(days) // 2], days[-1]]
    axis = "".join(f"<span>{d.month}/{d.day}</span>" for d in ticks)
    summary = f"近 {ACTIVITY_DAYS} 天共 {total:,} 則・{active_days} 天有發文・單日最多 {peak:,} 則"
    return (
        '<section class="card cand-card" aria-labelledby="cand-act-h">'
        f'<div class="section-head"><h2 id="cand-act-h">{ACTIVITY_DAYS} 天發文節奏</h2>'
        '<span class="muted xs">每日貼文數・GMT+8</span></div>'
        f'<p class="act-readout" aria-live="polite" data-default="{S.esc(summary)}">{S.esc(summary)}</p>'
        f'<div class="act-plot"><span class="act-max" aria-hidden="true">{peak:,}</span>'
        f'<ol class="act-bars" tabindex="0" aria-label="{ACTIVITY_DAYS} 天每日貼文數（方向鍵逐日檢視）">{"".join(bars)}</ol></div>'
        f'<div class="act-axis" aria-hidden="true">{axis}</div></section>'
    )


def _filters(posts: list[dict[str, Any]]) -> str:
    plats = Counter(p.get("platform") or "website" for p in posts)
    topics = Counter(t for p in posts for t in (p.get("topics") or []) if t)
    intents = Counter(_intent_type(p) for p in posts)
    plat_chips = [S.render_chip("全部", pressed=True, count=len(posts), attrs={"data-platform": ""})]
    plat_chips += [
        S.render_chip(S.PLATFORM_LABELS.get(p, p), pressed=False, icon_name=p, count=n, attrs={"data-platform": p})
        for p, n in sorted(plats.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    topic_chips = [
        S.render_chip(t, pressed=False, count=n, attrs={"data-topic": t})
        for t, n in sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    seg = ('<div class="seg" role="group" aria-label="發文動機">'
           '<button type="button" data-intent="" aria-pressed="true">全部</button>'
           + "".join(f'<button type="button" data-intent="{k}" aria-pressed="false">{v}'
                     f'<span class="chip-count">{intents.get(k, 0):,}</span></button>'
                     for k, v in S.INTENT_LABELS.items())
           + "</div>")
    return (
        '<form class="cand-filters card" role="search" aria-label="篩選貼文" onsubmit="return false">'
        '<div class="cand-filters-head"><h2 class="section-title">篩選</h2>'
        '<button class="btn btn-sm btn-ghost" type="reset" data-clear hidden>清除</button></div>'
        '<label class="sr-only" for="cand-q">關鍵字</label>'
        '<input class="input" id="cand-q" type="search" name="q" placeholder="搜尋貼文內容" autocomplete="off">'
        f'<div class="filter-row"><span class="filter-label">動機</span>{seg}</div>'
        f'<div class="filter-row"><span class="filter-label">平台</span><div class="chips" data-group="platform">{"".join(plat_chips)}</div></div>'
        f'<div class="filter-row"><span class="filter-label">議題</span><div class="chips" data-group="topic">{"".join(topic_chips)}</div></div>'
        '<p class="cand-note">議題可複選（符合任一即顯示）。議題與動機由 AI 分類，僅供參考。</p>'
        "</form>"
    )


def _write_pages(cid: str, posts: list[dict[str, Any]]) -> int:
    out = DATA_DIR / cid
    slim = [_slim(p) for p in posts]
    pages = max(1, -(-len(slim) // PAGE_SIZE))
    for i in range(pages):
        chunk = slim[i * PAGE_SIZE:(i + 1) * PAGE_SIZE]
        S.write_text(out / f"page-{i + 1}.json",
                     json.dumps({"version": 1, "page": i + 1, "posts": chunk}, ensure_ascii=False, separators=(",", ":")))
    S.write_text(out / "index.json", json.dumps(
        {"version": 1, "candidateId": cid, "pages": pages, "pageSize": PAGE_SIZE, "count": len(slim)},
        ensure_ascii=False, separators=(",", ":")))
    return pages


def _candidate_page(data, c: dict[str, Any], accounts: list[dict[str, Any]], post_counts: Counter,
                    now: dt.datetime) -> str:
    cid, city = c["id"], c.get("city") or ""
    path = f"/{city}/{cid}/"
    posts = data.posts_for(cid)
    pages = _write_pages(cid, posts)
    latest_iso = next((p.get("postedAt") for p in posts if p.get("postedAt")), None) or c.get("latestPostAt")
    city_full = S.city_label(city, False)

    actions = (
        f'<a class="btn btn-sm" href="/feeds/{cid}.xml">{S.icon("rss")}RSS</a>'
        f'<a class="btn btn-sm" href="/api/posts/{cid}.json">{S.icon("json")}JSON</a>'
        f'<a class="btn btn-sm btn-ghost" href="/source/{cid}/">{S.icon("status")}帳號驗證</a>'
    )
    hero = _profile_head(c, accounts, post_counts, False, actions, f"{city_full}市長候選人")

    ctx = data.post_ctx(show_city=False)
    ssr = "".join(S.render_post(p, ctx) for p in posts[:SSR_POSTS])
    if not posts:
        ssr = S.render_empty("尚無資料", "目前還沒有收錄這位候選人的公開貼文。")
    more_hidden = "" if len(posts) > SSR_POSTS else " hidden"
    timeline = (
        f'<section class="section cand-timeline" aria-labelledby="cand-feed-h" data-candidate="{S.esc(cid)}" '
        f'data-count="{len(posts)}" data-pages="{pages}" data-ssr="{min(len(posts), SSR_POSTS)}">'
        f'<div class="section-head"><h2 id="cand-feed-h">時間軸</h2>'
        f'<span class="muted small cand-count" aria-live="polite">顯示最新 {min(len(posts), SSR_POSTS):,} / {len(posts):,} 則</span></div>'
        '<div class="cand-timeline-grid">'
        f'<div class="cand-feed-col"><div class="feed" id="cand-feed">{ssr}</div>'
        '<div class="cand-empty" hidden>'
        + S.render_empty("目前的篩選條件下沒有貼文", "試著移除部分議題、平台或關鍵字篩選。",
                         '<button class="btn btn-sm" type="button" data-clear>清除篩選</button>')
        + "</div>"
        f'<div class="feed-more"><button class="btn" type="button" data-more{more_hidden}>載入更多</button>'
        f'<noscript><a class="btn" href="/api/posts/{cid}.json">完整貼文 JSON</a></noscript></div></div>'
        f'<aside class="cand-aside">{_filters(posts)}</aside>'
        "</div></section>"
    )

    body = (
        hero
        + _stat_tiles(posts, latest_iso, now)
        + f'<div class="cand-grid">{_activity_card(posts, now)}{_topics_card(data, cid)}</div>'
        + timeline
        + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(now.isoformat(), True))}（GMT+8）・'
          '本站為非官方觀測站，所有貼文皆連回原文。</p>'
    )

    party = _party_label(c)
    desc = (f"{c['name']}（{city_full}市長候選人・{party}）的官方公開發文時間軸：已收錄 {len(posts):,} 則，"
            "含議題比例、發文動機與 30 天發文節奏，所有貼文皆連回原文。")
    url = S.canonical(path)
    image = S.asset_abs(c.get("avatarUrl"))
    person = {
        "@type": "Person", "@id": url + "#person", "name": c["name"],
        "description": f"{city_full}市長候選人",
        "affiliation": {"@type": "PoliticalParty", "name": party} if c.get("party") else None,
        "homeLocation": {"@type": "City", "name": city_full},
        "sameAs": [S.safe_url(a.get("url"), internal=False) for a in accounts
                   if a.get("active", True) and S.safe_url(a.get("url"), internal=False)],
        "url": url,
    }
    if image:
        person["image"] = image if re.match(r"^https?://", image, re.I) else S.BASE_URL + image
    person = {k: v for k, v in person.items() if v}
    jsonld = {
        "@context": "https://schema.org", "@type": "ProfilePage", "url": url,
        "name": f"{c['name']}｜{S.SITE_NAME}", "inLanguage": "zh-Hant",
        "dateModified": now.isoformat(), "mainEntity": person,
        "isPartOf": {"@type": "WebSite", "name": S.SITE_NAME, "url": S.BASE_URL + "/"},
    }
    return S.layout("candidate", f"{c['name']}（{city_full}）", desc, path, body,
                    extra_css=["pages/candidate.css"], extra_js=["pages/candidate.js"],
                    jsonld=jsonld, og_image=image)


# ---------------------------------------------------------------------------
# /source/<id>/
# ---------------------------------------------------------------------------

def _source_page(data, c: dict[str, Any], accounts: list[dict[str, Any]], post_counts: Counter,
                 status_by_id: dict[str, dict[str, Any]], now: dt.datetime) -> str:
    cid, city = c["id"], c.get("city") or ""
    path = f"/source/{cid}/"
    actions = (
        f'<a class="btn btn-sm" href="/{city}/{cid}/">{S.icon("people")}候選人頁</a>'
        '<a class="btn btn-sm btn-ghost" href="/source/">全部來源</a>'
    )
    hero = _profile_head(c, accounts, post_counts, True, actions, "監看帳號明細")
    has_status = bool(status_by_id)

    rows = []
    for a in accounts:
        aid = a.get("id") or ""
        st = status_by_id.get(aid) or {}
        platform = a.get("platform") or "website"
        plat_label = S.PLATFORM_LABELS.get(platform, platform)
        active = a.get("active", True)
        label = _account_label(a)
        acct_url = S.safe_url(a.get("url"), internal=False)
        link = (f'<a href="{S.esc(acct_url)}" target="_blank" rel="noopener">{S.esc(label)}</a>'
                if acct_url else S.esc(label))
        disp = a.get("displayName")
        ident = (f'<div class="src-acct">{link}'
                 + (f'<span class="muted xs">{S.esc(disp)}</span>' if disp and disp != label else "")
                 + f'<span class="muted xs mono">{S.esc(aid)}</span></div>')
        role = ROLE_LABELS.get(a.get("role") or "", a.get("role") or "—")
        verif = a.get("verification") or ""
        verif_html = (f'<span class="src-verif" data-verif="{S.esc(verif)}" title="{S.esc(VERIFICATION_HINTS.get(verif, ""))}">'
                      f'{S.esc(VERIFICATION_LABELS.get(verif, verif or "—"))}</span>')
        if a.get("evidence"):
            verif_html += f'<p class="src-evidence">{S.esc(a["evidence"])}</p>'
        if not active:
            badge = S.render_badge("paused", "已停用")
        elif st:
            state, blabel = STATUS_BADGES.get(st.get("status") or "", ("paused", st.get("status") or "未知"))
            badge = S.render_badge(state, blabel)
        else:
            badge = S.render_badge("paused", "無狀態資料")
        reason = st.get("reason") or ""
        if reason:
            badge += f'<p class="src-reason">{S.esc(reason)}</p>'
        count = post_counts.get(aid, 0)
        last_items = st.get("lastItems")
        count_html = f"{count:,}" + (f'<span class="muted xs">本次 {int(last_items):,}</span>' if last_items is not None else "")
        err = st.get("lastError") or ""
        err_html = (f'<span class="src-error" title="{S.esc(err)}">{S.esc(err[:160])}</span>'
                    + (f'<span class="muted xs">{_time_html(st.get("lastErrorAt"))}</span>' if st.get("lastErrorAt") else "")
                    if err else '<span class="muted">—</span>')
        latest_iso = st.get("latestPostAt")
        if not latest_iso:
            latest_iso = next((p.get("postedAt") for p in data.posts_for(cid)
                               if p.get("sourceId") == aid and p.get("postedAt")), None)
        rows.append(
            f'<tr class="{"is-inactive" if not active else ""}" data-platform="{S.esc(platform)}">'
            f'<td><span class="src-plat">{S.icon(platform)}<span>{S.esc(plat_label)}</span></span></td>'
            f"<td>{ident}</td><td>{S.esc(role)}</td><td class=\"src-verif-cell\">{verif_html}</td>"
            f"<td>{badge}</td><td class=\"num\">{count_html}</td>"
            f'<td class="num">{_time_html(st.get("lastSuccess"))}</td>'
            f'<td class="num">{_time_html(latest_iso)}</td><td class="src-err-cell">{err_html}</td></tr>'
        )
    if rows:
        table = ('<div class="table-wrap"><table class="table src-table"><thead><tr>'
                 '<th scope="col">平台</th><th scope="col">帳號／顯示名</th><th scope="col">角色</th>'
                 '<th scope="col">驗證・佐證</th><th scope="col">狀態</th><th scope="col" class="num">已收錄</th>'
                 '<th scope="col" class="num">最近成功抓取</th><th scope="col" class="num">最新內容</th>'
                 '<th scope="col">目前錯誤</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>')
    else:
        table = S.render_empty("尚無資料", "這位候選人目前沒有監看中的帳號。")

    active_n = sum(1 for a in accounts if a.get("active", True))
    inactive_n = len(accounts) - active_n
    total_posts = sum(post_counts.values())
    summary = (f'<p class="cand-note">共 {len(accounts)} 個帳號：監看中 {active_n} 個'
               + (f"、已停用 {inactive_n} 個（歷史貼文保留）" if inactive_n else "")
               + f"；已收錄 {total_posts:,} 則貼文。時間皆為 GMT+8。</p>")
    status_note = ("" if has_status else
                   '<div class="notice" data-tone="warn"><p>目前沒有抓取狀態資料（status.json），狀態欄暫不顯示。</p></div>')
    method = (
        '<section class="section"><div class="section-head"><h2>驗證方式</h2>'
        '<a class="link-more" href="/about/">關於本站與資料原則 →</a></div>'
        '<div class="grid-3">'
        + "".join(f'<div class="card"><p class="card-title"><span class="src-verif" data-verif="{k}">{v}</span></p>'
                  f'<p class="card-meta">{VERIFICATION_HINTS[k]}。</p></div>' for k, v in VERIFICATION_LABELS.items())
        + "</div>"
        '<p class="cand-note src-method">本站只收錄候選人本人、競選團隊或現任職務的官方公開帳號；帳號角色分為'
        + "、".join(ROLE_LABELS.values())
        + '。狀態欄來自最近一次資料管線執行（<a href="/status/">資料來源狀態</a>）；「已收錄」為本站目前公開的已分類貼文數。'
        '發現帳號錯誤或遺漏，請<a href="' + S.esc(S.REPORT_URL) + '" target="_blank" rel="noopener">回報</a>。</p></section>'
    )
    body = (
        hero
        + '<section class="section src-section" aria-labelledby="src-h"><div class="section-head">'
          '<h2 id="src-h">監看帳號</h2>'
          f'<a class="link-more" href="/api/sources.json">sources.json →</a></div>'
        + summary + status_note + table + "</section>" + method
        + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(now.isoformat(), True))}（GMT+8）。</p>'
    )
    desc = (f"{c['name']}（{S.city_label(city, False)}）監看中的官方公開帳號、驗證方式與抓取狀態。")
    return S.layout("source-detail", f"{c['name']} 監看帳號", desc, path, body,
                    extra_css=["pages/candidate.css"], og_image=S.asset_abs(c.get("avatarUrl")))


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def _clean() -> None:
    for city in S.CITY_ORDER:
        shutil.rmtree(S.SITE_ROOT / city, ignore_errors=True)
    source_root = S.SITE_ROOT / "source"
    if source_root.is_dir():  # every /source/<id>/ dir (incl. stale non-roster ones); keep index.html
        for child in source_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
    shutil.rmtree(DATA_DIR, ignore_errors=True)


def render(data) -> None:
    _clean()
    now = data.generated_at
    status_by_id = {s["id"]: s for s in ((data.status or {}).get("sources") or []) if s.get("id")}
    csv_rows = _watchlist_rows()
    for c in data.candidates:
        cid = c["id"]
        accounts = _accounts(data, cid, status_by_id, csv_rows)
        post_counts = Counter(p.get("sourceId") for p in data.posts_for(cid))
        S.write_page(f"/{c.get('city')}/{cid}/", _candidate_page(data, c, accounts, post_counts, now))
        S.write_page(f"/source/{cid}/", _source_page(data, c, accounts, post_counts, status_by_id, now))
