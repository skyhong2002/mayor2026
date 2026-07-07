#!/usr/bin/env python3
"""Render site/index.html and per-candidate pages from site/templates/*.html.

Runs after build_public_data.py / build_spectrum.py so site/api/*.json is
already up to date; the actual data is fetched client-side by
site/assets/app.js, so this script only needs to fill in per-page
metadata (title, base path, candidate id) into the template shells.
"""

from __future__ import annotations

import hashlib

import classify_topics
import feed_common

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
TEMPLATES_DIR = SITE_ROOT / "templates"
API_DIR = SITE_ROOT / "api"


def asset_version() -> str:
    """Short content hash over the frontend assets, used as a cache-busting
    query string — CDN edges cache /assets/*.js for hours, so every deploy
    must reference a fresh URL."""
    digest = hashlib.sha256()
    for name in ("styles.css", "app.js"):
        digest.update((SITE_ROOT / "assets" / name).read_bytes())
    return digest.hexdigest()[:10]


def stamp_assets(html: str, version: str) -> str:
    return html.replace("assets/styles.css", f"assets/styles.css?v={version}").replace(
        "assets/app.js", f"assets/app.js?v={version}"
    )


def main() -> int:
    version = asset_version()

    def render(template: str) -> str:
        return stamp_assets(template, version)

    index_template = render((TEMPLATES_DIR / "index.html").read_text(encoding="utf-8"))
    (SITE_ROOT / "index.html").write_text(index_template, encoding="utf-8")

    source_index_template = render((TEMPLATES_DIR / "source-index.html").read_text(encoding="utf-8"))
    source_dir = SITE_ROOT / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "index.html").write_text(source_index_template, encoding="utf-8")

    status_template = render((TEMPLATES_DIR / "status.html").read_text(encoding="utf-8"))
    status_dir = SITE_ROOT / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    (status_dir / "index.html").write_text(status_template, encoding="utf-8")

    spectrum_template = render((TEMPLATES_DIR / "spectrum.html").read_text(encoding="utf-8"))
    spectrum_dir = SITE_ROOT / "spectrum"
    spectrum_dir.mkdir(parents=True, exist_ok=True)
    (spectrum_dir / "index.html").write_text(spectrum_template, encoding="utf-8")

    topic_template = render((TEMPLATES_DIR / "topic.html").read_text(encoding="utf-8"))
    for topic, slug in classify_topics.TOPIC_SLUGS.items():
        topic_dir = spectrum_dir / slug
        topic_dir.mkdir(parents=True, exist_ok=True)
        (topic_dir / "index.html").write_text(topic_template.replace("__TOPIC__", topic), encoding="utf-8")

        # /spectrum/topic/<slug>/ flattened into /spectrum/<slug>/; keep a
        # redirect so old links (bookmarks, RSS, search results) still land
        # somewhere.
        old_topic_dir = spectrum_dir / "topic" / slug
        old_topic_dir.mkdir(parents=True, exist_ok=True)
        target = f"../../{slug}/"
        redirect_html = (
            "<!DOCTYPE html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
            f"<meta http-equiv=\"refresh\" content=\"0; url={target}\">"
            f"<link rel=\"canonical\" href=\"{target}\">"
            f"<title>{topic}｜2026 市長官方來源觀測站</title></head>"
            f"<body>頁面已搬移，請見 <a href=\"{target}\">{topic} 議題比較頁</a>。</body></html>"
        )
        (old_topic_dir / "index.html").write_text(redirect_html, encoding="utf-8")

    source_detail_template = render((TEMPLATES_DIR / "source-detail.html").read_text(encoding="utf-8"))
    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})

    count = 0
    for candidate in candidates_payload.get("candidates", []):
        detail_dir = source_dir / candidate["id"]
        detail_dir.mkdir(parents=True, exist_ok=True)
        detail_html = (
            source_detail_template.replace("__CANDIDATE_NAME__", candidate["name"])
            .replace("__CANDIDATE_ID__", candidate["id"])
            .replace("__BASE__", "../../")
        )
        (detail_dir / "index.html").write_text(detail_html, encoding="utf-8")

        # /<city>/<candidate>/ merged into /source/<candidate>/; keep a redirect
        # so old links (bookmarks, RSS, search results) still land somewhere.
        old_page_dir = SITE_ROOT / candidate["city"] / candidate["id"]
        old_page_dir.mkdir(parents=True, exist_ok=True)
        target = f"../../source/{candidate['id']}/"
        redirect_html = (
            "<!DOCTYPE html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
            f"<meta http-equiv=\"refresh\" content=\"0; url={target}\">"
            f"<link rel=\"canonical\" href=\"{target}\">"
            f"<title>{candidate['name']}｜2026 市長官方來源觀測站</title></head>"
            f"<body>頁面已搬移，請見 <a href=\"{target}\">{candidate['name']} 的公開來源頁</a>。</body></html>"
        )
        (old_page_dir / "index.html").write_text(redirect_html, encoding="utf-8")
        count += 1

    print(f"generate_site_pages: wrote site/index.html, source index, and {count} candidate + source page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
