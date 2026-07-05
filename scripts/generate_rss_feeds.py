#!/usr/bin/env python3
"""Generate one RSS feed per candidate plus a combined feed."""

from __future__ import annotations

import xml.sax.saxutils as saxutils
from typing import Any

import feed_common

API_DIR = feed_common.PROJECT_ROOT / "site" / "api"
FEEDS_DIR = feed_common.PROJECT_ROOT / "site" / "feeds"
SITE_TITLE = "2026mayor - 六都市長候選人貼文監測站"


def rfc822(iso_timestamp: str) -> str:
    import datetime as dt
    import email.utils

    if not iso_timestamp:
        return ""
    try:
        parsed = dt.datetime.fromisoformat(iso_timestamp)
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return email.utils.format_datetime(parsed)


def render_rss(*, title: str, link: str, description: str, posts: list[dict[str, Any]]) -> str:
    items = []
    for post in posts:
        pub_date = rfc822(post.get("posted_at") or "")
        items.append(
            "    <item>\n"
            f"      <title>{saxutils.escape((post.get('text') or '')[:80])}</title>\n"
            f"      <link>{saxutils.escape(post.get('url') or '')}</link>\n"
            f"      <guid isPermaLink=\"false\">{saxutils.escape(post.get('id') or '')}</guid>\n"
            + (f"      <pubDate>{pub_date}</pubDate>\n" if pub_date else "")
            + f"      <description>{saxutils.escape(post.get('text') or '')}</description>\n"
            "    </item>"
        )
    items_xml = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>\n'
        f"  <title>{saxutils.escape(title)}</title>\n"
        f"  <link>{saxutils.escape(link)}</link>\n"
        f"  <description>{saxutils.escape(description)}</description>\n"
        f"{items_xml}\n"
        "</channel></rss>\n"
    )


def main() -> int:
    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})
    candidates = candidates_payload.get("candidates", [])
    posts_dir = API_DIR / "posts"

    FEEDS_DIR.mkdir(parents=True, exist_ok=True)

    all_posts: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_payload = feed_common.load_json(posts_dir / f"{candidate['id']}.json", {"posts": []})
        posts = candidate_payload.get("posts", [])
        all_posts.extend({**p, "candidate_id": candidate["id"], "candidate_name": candidate["name"]} for p in posts)

        rss_xml = render_rss(
            title=f"{candidate['name']}（{candidate['cityLabel']}）貼文更新",
            link=candidate.get("links", {}).get("website") or "",
            description=f"{candidate['name']} 在各平台的公開貼文合併時間軸。",
            posts=[{**p, "posted_at": p.get("postedAt"), "url": p.get("url"), "id": p.get("id"), "text": p.get("text")} for p in posts],
        )
        (FEEDS_DIR / f"{candidate['id']}.xml").write_text(rss_xml, encoding="utf-8")

    all_posts.sort(key=lambda p: p.get("postedAt") or "", reverse=True)
    combined_xml = render_rss(
        title=SITE_TITLE,
        link="",
        description="六都市長候選人公開貼文合併更新河道。",
        posts=[{**p, "posted_at": p.get("postedAt")} for p in all_posts[:100]],
    )
    (FEEDS_DIR / "updates.xml").write_text(combined_xml, encoding="utf-8")

    print(f"generate_rss_feeds: wrote {len(candidates)} candidate feed(s) + updates.xml to {FEEDS_DIR.relative_to(feed_common.PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
