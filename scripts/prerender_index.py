#!/usr/bin/env python3
"""Build-time prerender of the homepage's dynamic sections.

The homepage shell is filled in client-side by site/assets/app.js, which
means crawlers that don't execute JS only ever see "載入中...". This module
renders the same sections (stat row, city grid, latest feed) into static
HTML at build time so the first paint — and the Google index — carries real
content; app.js then re-renders on load with the exact same markup, PJAX
style, taking over interactivity (sorting, load-more, relative timestamps).

Markup here must mirror what app.js builds (same classes/structure) so the
JS takeover is visually seamless.
"""

from __future__ import annotations

import datetime as dt
from html import escape

import classify_topics
import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"

# Mirrors app.js PLATFORM_LABELS.
PLATFORM_LABELS = {
    "website": "官網",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "threads": "Threads",
    "youtube": "YouTube",
    "x": "X",
    "line_oa": "LINE 官方帳號",
    "line_openchat": "LINE 社群",
    "tiktok": "TikTok",
    "podcast": "Podcast",
}

INTENT_LABELS = {"self_initiated": "主動發文", "responsive": "回應他方觀點"}

FEED_PRERENDER_COUNT = 30  # matches FEED_PAGE_SIZE in app.js
FEED_COLUMNS = 3


def _format_taipei(iso: str) -> str:
    """Absolute Asia/Taipei timestamp; app.js swaps in relative time on load."""
    if not iso:
        return ""
    try:
        date = dt.datetime.fromisoformat(iso)
    except ValueError:
        return escape(iso)
    if date.tzinfo is None:
        date = date.replace(tzinfo=dt.timezone.utc)
    taipei = date.astimezone(dt.timezone(dt.timedelta(hours=8)))
    return taipei.strftime("%Y-%m-%d %H:%M")


def _avatar(name: str | None, avatar_url: str | None) -> str:
    if avatar_url:
        return (
            '<span class="source-avatar source-avatar-small">'
            f'<img src="{escape(avatar_url, quote=True)}" alt="{escape(name or "")}" loading="lazy">'
            "</span>"
        )
    return f'<span class="source-avatar source-avatar-small">{escape((name or "?")[:2])}</span>'


def _stat_row(candidates: list[dict]) -> str:
    total_posts = sum(c.get("postCount") or 0 for c in candidates)
    stats = [
        (str(len(candidates)), "監看候選人"),
        ("6", "直轄市"),
        (str(total_posts), "已收錄貼文"),
    ]
    return "".join(
        f'<div class="stat-card"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'
        for value, label in stats
    )


def _data_date(candidates: list[dict]) -> str:
    latest = max((c.get("latestPostAt") or "" for c in candidates), default="")
    return f"最後更新 {_format_taipei(latest)}" if latest else ""


def _city_grid(cities: list[dict], candidates_by_id: dict[str, dict]) -> str:
    # The JS default sort rotates randomly between neutral metrics to avoid
    # implying a stance; static HTML has to pick one, so use "最新更新"
    # (latestPostAt desc) — a data metric, not an editorial order.
    cards = []
    for city in cities:
        rows = sorted(
            (candidates_by_id[cid] for cid in city.get("candidateIds", []) if cid in candidates_by_id),
            key=lambda c: c.get("latestPostAt") or "",
            reverse=True,
        )
        if rows:
            links = "".join(
                f'<a href="source/{escape(c["id"], quote=True)}/">'
                '<span class="candidate-city-identity">'
                f'{_avatar(c.get("name"), c.get("avatarUrl"))}'
                f'<strong>{escape(c.get("name") or c["id"])}</strong></span>'
                f'<span class="data-date">{escape(c.get("party") or "未標註")} · {c.get("postCount") or 0} 則</span>'
                "</a>"
                for c in rows
            )
            body = f'<div class="candidate-city-list">{links}</div>'
        else:
            body = '<p class="empty-state">尚無候選人資料</p>'
        cards.append(
            '<article class="home-feed-card city-card">'
            f'<h3 class="city-card-title">{escape(city.get("label") or city.get("id", ""))}</h3>'
            f"{body}</article>"
        )
    return "".join(cards)


def _feed_card(post: dict, candidate: dict | None) -> str:
    accounts = (candidate or {}).get("accounts") or []
    account = next((a for a in accounts if a.get("id") == post.get("sourceId")), None)

    name = (
        (account or {}).get("displayName")
        or (candidate or {}).get("name")
        or post.get("candidateId", "")
    )
    avatar_url = (account or {}).get("avatarUrl") or (candidate or {}).get("avatarUrl")
    platform = post.get("platform") or ""
    platform_label = PLATFORM_LABELS.get(platform, platform)

    if account:
        account_label = account.get("handle") or account.get("url") or ""
    else:
        account_label = platform_label
    if account and account.get("url"):
        handle = (
            f'<a class="data-date" href="{escape(account["url"], quote=True)}" target="_blank" '
            f'rel="noopener" style="display:block;text-decoration:none">{escape(account_label)}</a>'
        )
    else:
        handle = f'<span class="data-date">{escape(account_label)}</span>'

    badge_url = (account or {}).get("url") or post.get("url") or ""
    # No inline platform SVG here (app.js injects it on takeover) — repeating
    # each icon per card would add tens of KB to index.html.
    badge = (
        f'<a class="platform-badge platform-badge-{escape(platform, quote=True)}" '
        f'href="{escape(badge_url, quote=True)}" target="_blank" rel="noopener" '
        f'title="{escape(platform_label, quote=True)}" aria-label="{escape(platform_label, quote=True)}"></a>'
    )

    image_url = post.get("imageUrl")
    body_class = "home-feed-body home-feed-body-no-title" + ("" if image_url else " home-feed-body-no-image")
    thumb = ""
    if image_url:
        aspect = post.get("imageAspect")
        style = f' style="--feed-image-aspect: {aspect}"' if aspect else ""
        thumb = (
            f'<span class="home-feed-thumb"{style}>'
            f'<img src="{escape(image_url, quote=True)}" alt="" loading="lazy"></span>'
        )

    topics_html = ""
    topics = post.get("topics") or []
    if topics:
        pills = []
        for topic in topics:
            slug = classify_topics.TOPIC_SLUGS.get(topic)
            if slug:
                pills.append(
                    f'<a class="pill" href="spectrum/{slug}/" style="text-decoration:none">{escape(topic)}</a>'
                )
            else:
                pills.append(f'<span class="pill">{escape(topic)}</span>')
        topics_html = f'<div class="entry-meta">{"".join(pills)}</div>'

    intent = post.get("postingIntent") or {"type": "self_initiated", "confidence": 0, "reason": "AI 分類處理中"}
    intent_type = intent.get("type") or "self_initiated"
    confidence = round((intent.get("confidence") or 0) * 100)
    intent_title = f"AI 判斷信心 {confidence}%" + (f"；{intent['reason']}" if intent.get("reason") else "")
    intent_html = (
        '<div class="entry-meta context-meta">'
        f'<span class="pill intent-pill intent-{escape(intent_type, quote=True)}" '
        f'title="{escape(intent_title, quote=True)}">'
        f"{escape(INTENT_LABELS.get(intent_type, intent_type))} {confidence}%</span></div>"
    )

    return (
        '<article class="home-feed-card">'
        '<div class="home-feed-source">'
        f'<div class="home-feed-source-main">{_avatar(name, avatar_url)}'
        f"<div><strong>{escape(name)}</strong>{handle}</div></div>"
        f"{badge}</div>"
        f'<div class="{body_class}">{thumb}'
        f'<p class="feed-latest-excerpt" style="margin:0">{escape(post.get("text") or "")}</p></div>'
        f"{topics_html}{intent_html}"
        '<div class="home-feed-footer">'
        f'<p class="entry-meta data-date">{_format_taipei(post.get("postedAt") or "")}</p>'
        f'<a class="feed-open-link" href="{escape(post.get("url") or "", quote=True)}" '
        'target="_blank" rel="noopener">打開原始貼文 ↗</a></div>'
        "</article>"
    )


def _latest_feed(posts: list[dict], candidates_by_id: dict[str, dict]) -> str:
    shown = posts[:FEED_PRERENDER_COUNT]
    columns: list[list[str]] = [[] for _ in range(FEED_COLUMNS)]
    for i, post in enumerate(shown):
        columns[i % FEED_COLUMNS].append(_feed_card(post, candidates_by_id.get(post.get("candidateId"))))
    column_html = "".join(f'<div class="feed-river-column">{"".join(cards)}</div>' for cards in columns)
    return f'<div class="feed-river">{column_html}</div>'


def render_sections() -> dict[str, str]:
    """Return prerendered inner HTML keyed by the template element id."""
    cities = feed_common.load_json(API_DIR / "cities.json", {"cities": []}).get("cities", [])
    candidates = feed_common.load_json(API_DIR / "sources.json", {"sources": []}).get("sources", [])
    latest = feed_common.load_json(API_DIR / "latest.json", {"posts": []}).get("posts", [])
    candidates_by_id = {c["id"]: c for c in candidates}

    return {
        "stat-row": _stat_row(candidates),
        "data-date": _data_date(candidates),
        "city-grid": _city_grid(cities, candidates_by_id),
        "latest-feed": _latest_feed(latest, candidates_by_id),
    }
