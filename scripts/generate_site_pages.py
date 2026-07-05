#!/usr/bin/env python3
"""Render site/index.html and per-candidate pages from site/templates/*.html.

Runs after build_public_data.py / build_spectrum.py so site/api/*.json is
already up to date; the actual data is fetched client-side by
site/assets/app.js, so this script only needs to fill in per-page
metadata (title, base path, candidate id) into the template shells.
"""

from __future__ import annotations

import feed_common

SITE_ROOT = feed_common.PROJECT_ROOT / "site"
TEMPLATES_DIR = SITE_ROOT / "templates"
API_DIR = SITE_ROOT / "api"


def main() -> int:
    index_template = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    (SITE_ROOT / "index.html").write_text(index_template, encoding="utf-8")

    source_index_template = (TEMPLATES_DIR / "source-index.html").read_text(encoding="utf-8")
    source_dir = SITE_ROOT / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "index.html").write_text(source_index_template, encoding="utf-8")

    candidate_template = (TEMPLATES_DIR / "candidate.html").read_text(encoding="utf-8")
    source_detail_template = (TEMPLATES_DIR / "source-detail.html").read_text(encoding="utf-8")
    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})

    count = 0
    for candidate in candidates_payload.get("candidates", []):
        page_dir = SITE_ROOT / candidate["city"] / candidate["id"]
        page_dir.mkdir(parents=True, exist_ok=True)
        html = (
            candidate_template.replace("__CANDIDATE_NAME__", candidate["name"])
            .replace("__CANDIDATE_ID__", candidate["id"])
            .replace("__BASE__", "../../")
        )
        (page_dir / "index.html").write_text(html, encoding="utf-8")

        detail_dir = source_dir / candidate["id"]
        detail_dir.mkdir(parents=True, exist_ok=True)
        detail_html = (
            source_detail_template.replace("__CANDIDATE_NAME__", candidate["name"])
            .replace("__CANDIDATE_ID__", candidate["id"])
            .replace("__BASE__", "../../")
        )
        (detail_dir / "index.html").write_text(detail_html, encoding="utf-8")
        count += 1

    print(f"generate_site_pages: wrote site/index.html, source index, and {count} candidate + source page(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
