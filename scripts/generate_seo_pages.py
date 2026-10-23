#!/usr/bin/env python3
"""Generate sitemap.xml and robots.txt for the public site."""

from __future__ import annotations

import datetime as dt
import os
from xml.sax.saxutils import escape

import feed_common

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
BASE_URL = os.environ.get("MAYOR_SITE_BASE_URL", "https://mayor2026.observe.tw").rstrip("/")

# Pages built from collected posts; their lastmod is the newest post on the site.
# /status/ is deliberately absent: it is a pipeline snapshot rendered noindex,
# and listing a noindex page in the sitemap sends search engines mixed signals.
FEED_PATHS = ["/", "/source/", "/spectrum/", "/policy-match/", "/feeds/", "/search/"]
# Hand-written pages with no data-derived modification time.
STATIC_PATHS = ["/about/"]


def lastmod(value: object) -> str | None:
    """W3C datetime for a post timestamp, or None when it is missing/invalid."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sitemap_entries(candidates: list[dict]) -> list[tuple[str, str | None]]:
    import classify_topics

    candidate_mods = {candidate["id"]: lastmod(candidate.get("latestPostAt")) for candidate in candidates}
    site_mod = max((mod for mod in candidate_mods.values() if mod), default=None)

    entries: list[tuple[str, str | None]] = [(path, site_mod) for path in FEED_PATHS]
    entries.extend((path, None) for path in STATIC_PATHS)
    entries.extend((f"/spectrum/{slug}/", site_mod) for slug in classify_topics.TOPIC_SLUGS.values())
    for candidate in candidates:
        # /<city>/<id>/ is the candidate timeline; /source/<id>/ lists the
        # candidate's monitored accounts. Both are canonical pages.
        mod = candidate_mods[candidate["id"]]
        entries.append((f"/{candidate['city']}/{candidate['id']}/", mod))
        entries.append((f"/source/{candidate['id']}/", mod))
    return entries


def render_sitemap(entries: list[tuple[str, str | None]]) -> str:
    urls = "\n".join(
        f"  <url><loc>{escape(BASE_URL + path)}</loc>"
        + (f"<lastmod>{mod}</lastmod>" if mod else "")
        + "</url>"
        for path, mod in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def main() -> int:
    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})
    entries = sitemap_entries(candidates_payload.get("candidates", []))
    (SITE_ROOT / "sitemap.xml").write_text(render_sitemap(entries), encoding="utf-8")

    robots = f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n"
    (SITE_ROOT / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"generate_seo_pages: sitemap with {len(entries)} URL(s) + robots.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
