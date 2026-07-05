#!/usr/bin/env python3
"""Generate sitemap.xml and robots.txt for the public site."""

from __future__ import annotations

import datetime as dt
import os

import feed_common

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
BASE_URL = os.environ.get("MAYOR_SITE_BASE_URL", "https://mayor2026.observe.tw").rstrip("/")


def main() -> int:
    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})
    candidates = candidates_payload.get("candidates", [])

    paths = ["/", "/source/", "/status/", "/spectrum/"]
    import classify_topics

    paths.extend(f"/spectrum/topic/{slug}/" for slug in classify_topics.TOPIC_SLUGS.values())
    for candidate in candidates:
        paths.append(f"/{candidate['city']}/{candidate['id']}/")
        paths.append(f"/source/{candidate['id']}/")

    today = dt.date.today().isoformat()
    urls = "\n".join(
        f"  <url><loc>{BASE_URL}{path}</loc><lastmod>{today}</lastmod></url>" for path in paths
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    (SITE_ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    robots = f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n"
    (SITE_ROOT / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"generate_seo_pages: sitemap with {len(paths)} URL(s) + robots.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
