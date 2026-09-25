#!/usr/bin/env python3
"""Render every HTML page of the public site.

Runs after build_public_data.py / build_spectrum.py / build_qualitative.py /
build_status_page.py so site/api/*.json is current. Each page family lives in
scripts/render/<name>.py and exposes ``render(data) -> None``; a module owns
(and cleans) its own output directories. Missing modules are skipped with a
warning so the site can be rebuilt incrementally.

    python3 scripts/generate_site_pages.py          # all pages
    python3 scripts/generate_site_pages.py --kit    # also the dev-only /_kit/ page
"""

from __future__ import annotations

import importlib
import shutil
import sys
import traceback
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from render import data as data_mod  # noqa: E402
from render import shell  # noqa: E402

PAGE_MODULES = ["home", "candidate", "directory", "spectrum", "policy", "status", "search"]


def asset_version() -> str:
    """Cache-busting hash over shipped CSS/JS (kept for build_status_page)."""
    return shell.asset_hash()


def write_topic_redirects() -> int:
    """/spectrum/topic/<slug>/ → /spectrum/<slug>/ (old URLs stay alive)."""
    for topic, slug in shell.TOPIC_SLUGS.items():
        shell.write_redirect(f"/spectrum/topic/{slug}/", f"/spectrum/{slug}/", f"{topic}議題比較")
    return len(shell.TOPIC_SLUGS)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    shell.write_icons_js()
    data = data_mod.load(refresh=True)
    if not data.candidates:
        print("generate_site_pages: site/api/candidates.json missing or empty", file=sys.stderr)
        return 1

    rendered, missing, failed = [], [], []
    for name in PAGE_MODULES:
        try:
            module = importlib.import_module(f"render.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"render.{name}":
                raise
            missing.append(name)
            print(f"generate_site_pages: warning: render/{name}.py not found; skipped", file=sys.stderr)
            continue
        try:
            module.render(data)
            rendered.append(name)
        except Exception:  # keep building the other pages, fail at the end
            traceback.print_exc()
            failed.append(name)

    redirects = write_topic_redirects()

    if missing or "--kit" in argv:
        from render import kit
        kit.render(data)
        rendered.append("_kit")
    else:  # dev-only page must never reach a published snapshot
        shutil.rmtree(shell.SITE_ROOT / "_kit", ignore_errors=True)

    print(f"generate_site_pages: rendered {', '.join(rendered) or 'nothing'}; "
          f"{redirects} topic redirect(s); assets v={asset_version()}")
    if failed:
        print(f"generate_site_pages: FAILED modules: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
