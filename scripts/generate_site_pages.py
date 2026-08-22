#!/usr/bin/env python3
"""Render site/index.html and per-candidate pages from site/templates/*.html.

Runs after build_public_data.py / build_spectrum.py so site/api/*.json is
already up to date. Every page's dynamic sections are prerendered into
static HTML via prerender_pages.py (so crawlers without JS see real
content); site/assets/app.js re-renders the same markup on load and takes
over interactivity.
"""

from __future__ import annotations

import hashlib
import re

import classify_topics
import feed_common
import prerender_pages

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


def inject_sections(html: str, sections: dict[str, str], page: str) -> str:
    """Replace the inner HTML of each prerender target.

    Keys are element ids; a "tbody:<table-id>" key targets the <tbody> of
    that table instead. Raises if a target is missing or ambiguous so
    template drift fails the build instead of silently shipping an empty
    shell.
    """
    for key, inner in sections.items():
        if key.startswith("tbody:"):
            table_id = key.split(":", 1)[1]
            pattern = re.compile(
                rf'(<table\b[^>]*\bid="{re.escape(table_id)}"[^>]*>.*?<tbody>).*?(</tbody>)', re.S
            )
            close_group = 2
        else:
            pattern = re.compile(
                rf'(<(\w+)\b[^>]*\bid="{re.escape(key)}"[^>]*>).*?(</\2>)', re.S
            )
            close_group = 3
        html, count = pattern.subn(
            lambda m, inner=inner, g=close_group: m.group(1) + inner + m.group(g), html, count=1
        )
        if count != 1:
            raise SystemExit(f"generate_site_pages: prerender target {key!r} not found in {page} template")
    return html


def main() -> int:
    version = asset_version()
    data = prerender_pages.load_data()

    def render(template_name: str, sections: dict[str, str] | None = None) -> str:
        html = stamp_assets((TEMPLATES_DIR / f"{template_name}.html").read_text(encoding="utf-8"), version)
        if sections:
            html = inject_sections(html, sections, template_name)
        return html

    (SITE_ROOT / "index.html").write_text(render("index", prerender_pages.render_index(data)), encoding="utf-8")

    source_dir = SITE_ROOT / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "index.html").write_text(
        render("source-index", prerender_pages.render_source_index(data)), encoding="utf-8"
    )

    # /status/ is rendered directly by build_status_page.py (it needs live
    # collector health data, not just static template text).

    spectrum_dir = SITE_ROOT / "spectrum"
    spectrum_dir.mkdir(parents=True, exist_ok=True)
    (spectrum_dir / "index.html").write_text(
        render("spectrum", prerender_pages.render_spectrum(data)), encoding="utf-8"
    )

    policy_dir = SITE_ROOT / "policy-match"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "index.html").write_text(
        render("policy-match", prerender_pages.render_policy_match(data)), encoding="utf-8"
    )

    for topic, slug in classify_topics.TOPIC_SLUGS.items():
        topic_dir = spectrum_dir / slug
        topic_dir.mkdir(parents=True, exist_ok=True)
        topic_html = render("topic", prerender_pages.render_topic(data, topic)).replace("__TOPIC__", topic)
        (topic_dir / "index.html").write_text(topic_html, encoding="utf-8")

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

    candidates_payload = feed_common.load_json(API_DIR / "candidates.json", {"candidates": []})

    count = 0
    for candidate in candidates_payload.get("candidates", []):
        detail_dir = source_dir / candidate["id"]
        detail_dir.mkdir(parents=True, exist_ok=True)
        detail_html = (
            render("source-detail", prerender_pages.render_source_detail(data, candidate["id"]))
            .replace("__CANDIDATE_NAME__", candidate["name"])
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

    print(f"generate_site_pages: wrote index, source, spectrum, policy-match, topic, and {count} candidate page(s), all prerendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
