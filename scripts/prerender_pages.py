#!/usr/bin/env python3
"""Build-time prerender of every page's dynamic sections.

All public pages are filled in client-side by site/assets/app.js, which
means crawlers that don't execute JS only ever see "載入中...". This module
renders the same sections into static HTML at build time so the first
paint — and the Google index — carries real content; app.js then re-renders
on load with the exact same markup, PJAX style, taking over interactivity
(sorting, filters, load-more, relative timestamps, charts).

Markup here must mirror what app.js builds (same classes/structure) so the
JS takeover is visually seamless. Interactive-only widgets (sort/filter
chips, the candidate picker, canvas charts) are left for app.js; only
content is prerendered.
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

# Mirrors app.js TOPIC_COLORS.
TOPIC_COLORS = {
    "交通": "#0f766e",
    "住宅": "#b87921",
    "社福": "#c85f44",
    "環境": "#4d8a56",
    "教育": "#3b6ea5",
    "經濟": "#7c5cad",
    "治安": "#a54d68",
    "醫療": "#5c6a63",
    "競選": "#d46a9e",
    "體育": "#45a0c9",
    "文化觀光": "#c9a227",
    "兩岸外交": "#8a5a2d",
    "防災": "#e07b39",
    "議會監督": "#7a7f2a",
    "生活": "#b8bdb9",
}

FEED_PRERENDER_COUNT = 30  # matches FEED_PAGE_SIZE in app.js
FEED_COLUMNS = 3


def _js_round(value: float) -> int:
    """Math.round semantics (half away from zero for positives) — Python's
    round() is banker's rounding and would drift 1% off the JS re-render."""
    return int(value + 0.5)


def load_data() -> dict:
    """Load every API payload the prerenderers need, once."""
    sources = feed_common.load_json(API_DIR / "sources.json", {"sources": []}).get("sources", [])
    data = {
        "cities": feed_common.load_json(API_DIR / "cities.json", {"cities": []}).get("cities", []),
        "sources": sources,
        "sources_by_id": {s["id"]: s for s in sources},
        "latest": feed_common.load_json(API_DIR / "latest.json", {"posts": []}).get("posts", []),
        "spectrum": feed_common.load_json(API_DIR / "spectrum.json", {"candidates": []}),
        "topic_index": feed_common.load_json(API_DIR / "topic-index.json", {"posts": []}),
        "topic_details": feed_common.load_json(API_DIR / "topic-details.json", {"topics": {}}),
        "policy": feed_common.load_json(API_DIR / "policy-match.json", {"questions": []}),
        "posts_by_candidate": {},
    }
    for source in sources:
        payload = feed_common.load_json(API_DIR / "posts" / f"{source['id']}.json", {"posts": []})
        data["posts_by_candidate"][source["id"]] = payload.get("posts", [])
    return data


def _format_taipei(iso: str) -> str:
    """Absolute Asia/Taipei timestamp; app.js swaps in relative time on load."""
    if not iso:
        return ""
    try:
        date = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return escape(iso)
    if date.tzinfo is None:
        date = date.replace(tzinfo=dt.timezone.utc)
    taipei = date.astimezone(dt.timezone(dt.timedelta(hours=8)))
    return taipei.strftime("%Y-%m-%d %H:%M")


def _avatar(name: str | None, avatar_url: str | None, base: str, small: bool = True) -> str:
    cls = "source-avatar source-avatar-small" if small else "source-avatar"
    if avatar_url:
        return (
            f'<span class="{cls}">'
            f'<img src="{escape(base + avatar_url, quote=True)}" alt="{escape(name or "")}" loading="lazy">'
            "</span>"
        )
    return f'<span class="{cls}">{escape((name or "?")[:2])}</span>'


def _candidate_sort_key(candidate: dict):
    # The JS default sort rotates randomly between neutral metrics to avoid
    # implying a stance; static HTML has to pick one, so use "最新更新"
    # (latestPostAt desc) — a data metric, not an editorial order.
    return candidate.get("latestPostAt") or ""


def _account_icon_link(account: dict) -> str:
    # No inline platform SVG (app.js injects it on takeover) — repeating the
    # icons across every row/card would add tens of KB per page.
    platform = account.get("platform") or ""
    label = PLATFORM_LABELS.get(platform, platform)
    return (
        f'<a class="directory-link-icon platform-badge platform-badge-{escape(platform, quote=True)}" '
        f'href="{escape(account.get("url") or "", quote=True)}" target="_blank" rel="noopener" '
        f'title="{escape(label, quote=True)}" aria-label="{escape(label, quote=True)}"></a>'
    )


def _feed_card(post: dict, candidate: dict | None, base: str) -> str:
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
            f'<img src="{escape(base + image_url, quote=True)}" alt="" loading="lazy"></span>'
        )

    topics_html = ""
    topics = post.get("topics") or []
    if topics:
        pills = []
        for topic in topics:
            slug = classify_topics.TOPIC_SLUGS.get(topic)
            if slug:
                pills.append(
                    f'<a class="pill" href="{base}spectrum/{slug}/" style="text-decoration:none">{escape(topic)}</a>'
                )
            else:
                pills.append(f'<span class="pill">{escape(topic)}</span>')
        topics_html = f'<div class="entry-meta">{"".join(pills)}</div>'

    intent = post.get("postingIntent") or {"type": "self_initiated", "confidence": 0, "reason": "AI 分類處理中"}
    intent_type = intent.get("type") or "self_initiated"
    confidence = _js_round((intent.get("confidence") or 0) * 100)
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
        f'<div class="home-feed-source-main">{_avatar(name, avatar_url, base)}'
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


def _river(posts: list[dict], sources_by_id: dict[str, dict], base: str) -> str:
    if not posts:
        return '<div class="feed-river"><p class="empty-state">尚無收錄貼文。</p></div>'
    shown = posts[:FEED_PRERENDER_COUNT]
    columns: list[list[str]] = [[] for _ in range(FEED_COLUMNS)]
    for i, post in enumerate(shown):
        columns[i % FEED_COLUMNS].append(_feed_card(post, sources_by_id.get(post.get("candidateId")), base))
    column_html = "".join(f'<div class="feed-river-column">{"".join(cards)}</div>' for cards in columns)
    return f'<div class="feed-river">{column_html}</div>'


# ---------------------------------------------------------------------------
# / (homepage)


def render_index(data: dict) -> dict[str, str]:
    candidates = data["sources"]
    total_posts = sum(c.get("postCount") or 0 for c in candidates)
    stat_row = "".join(
        f'<div class="stat-card"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'
        for value, label in [
            (str(len(candidates)), "監看候選人"),
            ("6", "直轄市"),
            (str(total_posts), "已收錄貼文"),
        ]
    )

    latest_at = max((c.get("latestPostAt") or "" for c in candidates), default="")
    data_date = f"最後更新 {_format_taipei(latest_at)}" if latest_at else ""

    cards = []
    for city in data["cities"]:
        rows = sorted(
            (data["sources_by_id"][cid] for cid in city.get("candidateIds", []) if cid in data["sources_by_id"]),
            key=_candidate_sort_key,
            reverse=True,
        )
        if rows:
            links = "".join(
                f'<a href="source/{escape(c["id"], quote=True)}/">'
                '<span class="candidate-city-identity">'
                f'{_avatar(c.get("name"), c.get("avatarUrl"), "")}'
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

    return {
        "stat-row": stat_row,
        "data-date": data_date,
        "city-grid": "".join(cards),
        "latest-feed": _river(data["latest"], data["sources_by_id"], ""),
    }


# ---------------------------------------------------------------------------
# /source/ (directory)


def render_source_index(data: dict) -> dict[str, str]:
    rows = []
    for source in sorted(data["sources"], key=_candidate_sort_key, reverse=True):
        links = "".join(_account_icon_link(a) for a in source.get("accounts") or [])
        rows.append(
            "<tr>"
            '<td class="directory-source-cell">'
            f'<a class="directory-source-identity" href="{escape(source["id"], quote=True)}/" '
            'style="text-decoration:none;color:inherit">'
            f'{_avatar(source.get("name"), source.get("avatarUrl"), "../")}'
            f'<span class="directory-source-name-block">{escape(source.get("name") or source["id"])}</span></a></td>'
            f'<td class="directory-link-cell">{links}</td>'
            f'<td>{_format_taipei(source.get("latestPostAt") or "") or "—"}</td>'
            f'<td>{escape(source.get("cityLabel") or "")}</td>'
            f'<td>{escape(source.get("party") or "未標註")}</td>'
            "</tr>"
        )
    return {
        "source-count": f"{len(data['sources'])} 位候選人",
        "tbody:source-table": "".join(rows),
    }


# ---------------------------------------------------------------------------
# /source/<id>/ (candidate detail)


def render_source_detail(data: dict, candidate_id: str) -> dict[str, str]:
    base = "../../"
    source = data["sources_by_id"].get(candidate_id, {})
    posts = data["posts_by_candidate"].get(candidate_id, [])

    by_account: dict[str, dict] = {}
    for post in posts:
        bucket = by_account.setdefault(post.get("sourceId"), {"count": 0, "latest": ""})
        bucket["count"] += 1
        if (post.get("postedAt") or "") > bucket["latest"]:
            bucket["latest"] = post.get("postedAt") or ""

    account_rows = []
    for account in source.get("accounts") or []:
        platform = account.get("platform") or ""
        stats = by_account.get(account.get("id"))
        account_rows.append(
            "<tr>"
            f"<td>{_account_icon_link(account)} {escape(PLATFORM_LABELS.get(platform, platform))}</td>"
            '<td><a class="score-source-link" '
            f'href="{escape(account.get("url") or "", quote=True)}" target="_blank" rel="noopener" '
            f'title="{escape(account.get("url") or "", quote=True)}">{escape(account.get("url") or "")}</a></td>'
            f'<td>{stats["count"] if stats else 0}</td>'
            f'<td>{_format_taipei(stats["latest"]) if stats else "—"}</td>'
            "</tr>"
        )

    spectrum_entry = next(
        (c for c in data["spectrum"].get("candidates", []) if c.get("candidateId") == candidate_id), None
    )
    proportions = (spectrum_entry or {}).get("topicProportions") or {}
    keyword_rows_by_topic = data["topic_details"].get("topics", {})
    breakdown_rows = []
    for topic, value in sorted(proportions.items(), key=lambda kv: kv[1], reverse=True):
        slug = classify_topics.TOPIC_SLUGS.get(topic)
        if slug:
            name_node = (
                f'<a class="topic-breakdown-name" href="{base}spectrum/{slug}/" '
                f'title="看「{escape(topic, quote=True)}」議題的候選人比較">{escape(topic)}</a>'
            )
        else:
            name_node = f'<span class="topic-breakdown-name">{escape(topic)}</span>'
        keywords = (keyword_rows_by_topic.get(topic) or {}).get(candidate_id) or []
        chips = ""
        if keywords:
            pills = "".join(
                f'<span class="pill">{escape(str(kw))} ×{count}</span>' for kw, count in keywords[:6]
            )
            chips = f'<div class="entry-meta">{pills}</div>'
        color = TOPIC_COLORS.get(topic, "#9aa19d")
        breakdown_rows.append(
            '<div class="topic-breakdown-row">'
            f'<div class="topic-breakdown-head">{name_node}'
            f'<span class="data-date">{_js_round(value * 100)}%</span></div>'
            '<div class="topic-breakdown-track">'
            f'<i style="width: {max(value * 100, 1.5):.1f}%; background: {color}"></i></div>'
            f"{chips}</div>"
        )
    breakdown = "".join(breakdown_rows) or '<p class="empty-state">尚無足夠貼文計算議題細項。</p>'

    if posts:
        post_list = _river(posts, {candidate_id: source}, base)
    else:
        post_list = '<p class="empty-state">沒有符合篩選條件的貼文。</p>'

    return {
        "candidate-city": f"{source.get('cityLabel') or ''}市長候選人",
        "candidate-name": source.get("name") or candidate_id,
        "candidate-party": f"{source.get('party') or '未標註'} · 已收錄 {source.get('postCount') or 0} 則公開貼文",
        "hero-avatar": (
            f'<img src="{escape(base + source["avatarUrl"], quote=True)}" '
            f'alt="{escape(source.get("name") or "")}" loading="lazy">'
            if source.get("avatarUrl")
            else escape((source.get("name") or "?")[:2])
        ),
        "timeline-count": f"顯示 {len(posts)} / {len(posts)} 則",
        "topic-breakdown": breakdown,
        "post-list": post_list,
        "tbody:account-table": "".join(account_rows),
    }


# ---------------------------------------------------------------------------
# /spectrum/


def _compute_spectrum(topic_index: dict) -> dict[str, dict]:
    """Mirrors app.js computeSpectrum with the default filter state:
    all time, all intents, fallback topic (日常生活) excluded."""
    fallback = topic_index.get("fallbackTopic")
    per_candidate: dict[str, dict] = {}
    for post in topic_index.get("posts", []):
        totals = None
        for topic, score in (post.get("topicScores") or {}).items():
            if topic == fallback:
                continue
            bucket = per_candidate.setdefault(post["candidateId"], {"totals": {}, "count": 0})
            bucket["totals"][topic] = bucket["totals"].get(topic, 0) + score
            totals = bucket
        if totals:
            totals["count"] += 1
    result = {}
    for candidate_id, bucket in per_candidate.items():
        grand = sum(bucket["totals"].values())
        proportions = (
            {topic: value / grand for topic, value in bucket["totals"].items()} if grand > 0 else {}
        )
        result[candidate_id] = proportions
    return result


def render_spectrum(data: dict) -> dict[str, str]:
    spectrum = _compute_spectrum(data["topic_index"])

    totals: dict[str, float] = {}
    for proportions in spectrum.values():
        for topic, value in proportions.items():
            totals[topic] = totals.get(topic, 0) + value
    topics = sorted(totals, key=lambda t: totals[t], reverse=True)
    if not topics:
        return {"spectrum-cities": '<p class="empty-state">目前的篩選條件下沒有任何議題資料。</p>'}

    head_cells = ['<th>候選人</th>']
    for topic in topics:
        slug = classify_topics.TOPIC_SLUGS.get(topic)
        if slug:
            head_cells.append(
                '<th class="spectrum-topic-head">'
                f'<a class="spectrum-topic-link" href="../spectrum/{slug}/" '
                f'title="看「{escape(topic, quote=True)}」議題的候選人比較">{escape(topic)}</a></th>'
            )
        else:
            head_cells.append(f'<th class="spectrum-topic-head">{escape(topic)}</th>')

    body_rows = []
    for city in data["cities"]:
        if not city.get("candidateIds"):
            continue
        body_rows.append(
            f'<tr><td class="spectrum-city-cell" colspan="{len(topics) + 1}">{escape(city.get("label") or "")}</td></tr>'
        )
        ordered = sorted(
            (data["sources_by_id"][cid] for cid in city["candidateIds"] if cid in data["sources_by_id"]),
            key=_candidate_sort_key,
            reverse=True,
        )
        for source in ordered:
            proportions = spectrum.get(source["id"]) or {}
            row_max = max(proportions.values(), default=0)
            cells = [
                '<td class="directory-source-cell">'
                f'<a class="spectrum-identity" href="../source/{escape(source["id"], quote=True)}/">'
                f'{_avatar(source.get("name"), source.get("avatarUrl"), "../")}'
                f'<div><strong>{escape(source.get("name") or source["id"])}</strong>'
                f'<span class="data-date">{escape(source.get("party") or "未標註")} · {source.get("postCount") or 0} 則</span>'
                "</div></a></td>"
            ]
            for topic in topics:
                value = proportions.get(topic, 0)
                if not proportions:
                    cells.append('<td class="spectrum-cell" style="color: var(--muted)">—</td>')
                elif value > 0:
                    ratio = value / (row_max or 1)
                    styles = [f"background: rgba(15, 118, 110, {0.08 + 0.72 * ratio:.3f})"]
                    if ratio > 0.55:
                        styles.append("color: #fff")
                    max_class = " spectrum-cell-max" if value == row_max else ""
                    cells.append(
                        f'<td class="spectrum-cell{max_class}" style="{"; ".join(styles)}">'
                        f"{_js_round(value * 100)}%</td>"
                    )
                else:
                    cells.append('<td class="spectrum-cell" style="color: #c4ccc6">·</td>')
            body_rows.append(f"<tr>{''.join(cells)}</tr>")

    table = (
        '<div class="directory-table-list"><table class="score-table spectrum-table">'
        f'<thead><tr>{"".join(head_cells)}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table></div>'
        '<p class="data-date" style="margin-top: 12px">顏色深淺＝該議題佔該候選人議題發文的比例（每列各自正規化）；'
        "粗框＝該候選人聲量最高的議題；「·」＝無相關貼文。點表頭議題名稱可看該議題的跨候選人比較。</p>"
    )
    return {"spectrum-cities": table}


# ---------------------------------------------------------------------------
# /spectrum/<topic>/


def render_topic(data: dict, topic: str) -> dict[str, str]:
    base = "../../"
    post_ids_by_candidate: dict[str, set] = {}
    for post in data["topic_index"].get("posts", []):
        if (post.get("topicScores") or {}).get(topic):
            post_ids_by_candidate.setdefault(post["candidateId"], set()).add(post["id"])
    candidate_ids = sorted(post_ids_by_candidate, key=lambda cid: len(post_ids_by_candidate[cid]), reverse=True)
    total = sum(len(ids) for ids in post_ids_by_candidate.values())

    summary = (
        f"{len(candidate_ids)} 位候選人共 {total} 則相關貼文。"
        "可複選候選人縮小比較範圍，或直接看全部並排比較。"
    )
    if not candidate_ids:
        return {
            "topic-summary": summary,
            "topic-candidates": '<p class="empty-state">目前沒有這個議題的貼文。</p>',
        }

    keywords_by_candidate = data["topic_details"].get("topics", {}).get(topic, {})
    headings = []
    for candidate_id in candidate_ids:
        source = data["sources_by_id"].get(candidate_id)
        if not source:
            continue
        keywords = keywords_by_candidate.get(candidate_id) or []
        chips = ""
        if keywords:
            pills = "".join(
                f'<span class="pill">{escape(str(kw))} ×{count}</span>' for kw, count in keywords[:8]
            )
            chips = f'<div class="entry-meta">{pills}</div>'
        headings.append(
            '<div class="topic-candidate-heading">'
            f'<a class="spectrum-identity" href="{base}source/{escape(candidate_id, quote=True)}/">'
            f'{_avatar(source.get("name"), source.get("avatarUrl"), base)}'
            f'<div><strong>{escape(source.get("name") or candidate_id)}</strong>'
            f'<span class="data-date">{escape(source.get("cityLabel") or "")} · '
            f'{escape(source.get("party") or "未標註")} · 本議題 {len(post_ids_by_candidate[candidate_id])} 則</span>'
            f"</div></a>{chips}</div>"
        )

    merged = []
    for candidate_id in candidate_ids:
        wanted = post_ids_by_candidate[candidate_id]
        merged.extend(p for p in data["posts_by_candidate"].get(candidate_id, []) if p.get("id") in wanted)
    merged.sort(key=lambda p: p.get("postedAt") or "", reverse=True)

    sections = (
        f'<div class="topic-summaries">{"".join(headings)}</div>'
        '<p class="section-kicker" style="margin-top: 28px">Posts</p>'
        "<h2>全部貼文</h2>"
        f'<div class="latest-feed-grid" style="margin-top: 14px">{_river(merged, data["sources_by_id"], base)}</div>'
    )
    return {"topic-summary": summary, "topic-candidates": sections}


# ---------------------------------------------------------------------------
# /policy-match/


def render_policy_match(data: dict) -> dict[str, str]:
    policy = data["policy"]
    blocks = []
    for question in policy.get("questions", []):
        choices = "".join(
            f'<button class="policy-choice">{escape(choice.get("label") or "")}</button>'
            for choice in question.get("choices", [])
        )
        blocks.append(
            '<section class="policy-question">'
            f'<h2>{escape(question.get("prompt") or "")}</h2>'
            f'<p class="data-date">最多選 {question.get("maxChoices")} 項</p>'
            f'<div class="policy-choice-grid">{choices}</div></section>'
        )
    blocks.append('<button class="feed-load-more-button policy-submit">查看匹配結果</button>')
    if policy.get("methodology"):
        blocks.append(f'<p class="data-date">{escape(policy["methodology"])}</p>')
    return {"policy-questions": "".join(blocks)}
