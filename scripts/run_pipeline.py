#!/usr/bin/env python3
"""Run the standalone public data pipeline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
DEFAULT_LOCK_FILE = PROJECT_ROOT / "state" / "run_pipeline.lock"


def acquire_lock(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"Pipeline already running (lock={path}); skipping this run.")
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid()}, handle)
    return True


def release_lock(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def run(args: list[str], *, optional: bool = False) -> None:
    result = subprocess.run(args, cwd=PROJECT_ROOT)
    if result.returncode:
        message = f"Pipeline step failed with exit code {result.returncode}: {' '.join(args)}"
        if optional:
            print(message, file=sys.stderr)
        else:
            raise subprocess.CalledProcessError(result.returncode, args)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-watch", action="store_true", help="Skip fetching new posts; rebuild site from existing data only.")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-facebook-apify", action="store_true")
    parser.add_argument("--skip-official-site", action="store_true")
    parser.add_argument("--max-post-age-days", type=int, default=30)
    parser.add_argument("--publish-pages", action="store_true")
    parser.add_argument("--pages-no-push", action="store_true")
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK_FILE)
    parser.add_argument("--no-lock", action="store_true")
    args = parser.parse_args()

    lock_path = args.lock_file if args.lock_file.is_absolute() else PROJECT_ROOT / args.lock_file
    if not args.no_lock and not acquire_lock(lock_path):
        return 0

    try:
        run([PYTHON, "scripts/build_social_sources.py"])

        if not args.skip_watch:
            run([PYTHON, "scripts/rsshub_fetcher.py"], optional=True)
            if not args.skip_youtube:
                run([PYTHON, "scripts/youtube_ytdlp_fetcher.py"], optional=True)
            if not args.skip_facebook_apify:
                run([PYTHON, "scripts/apify_facebook_fetcher.py"], optional=True)
            if not args.skip_official_site:
                run([PYTHON, "scripts/official_site_fetcher.py"], optional=True)
            run([PYTHON, "scripts/social_feed_watchdog.py", "--max-post-age-days", str(args.max_post_age_days)])

        run([PYTHON, "scripts/fetch_media_cache.py"], optional=True)
        run([PYTHON, "scripts/build_public_data.py"])
        run([PYTHON, "scripts/build_spectrum.py"])
        run([PYTHON, "scripts/generate_rss_feeds.py"])
        run([PYTHON, "scripts/generate_site_pages.py"])
        run([PYTHON, "scripts/validate_public_outputs.py"])

        if args.publish_pages:
            pages_args = [PYTHON, "scripts/publish_github_pages.py"]
            if args.pages_no_push:
                pages_args.append("--no-push")
            run(pages_args)
    finally:
        if not args.no_lock:
            release_lock(lock_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
