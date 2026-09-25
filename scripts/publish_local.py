#!/usr/bin/env python3
"""Publish the generated ``site/`` snapshot to a local release directory served by Caddy.

Layout (mirrors chumei.observe.tw):

    <publish_root>/releases/<UTC timestamp>-<git sha>/   full copy of site/
    <publish_root>/current  -> releases/<newest>
    <publish_root>/previous -> releases/<the one before>

The web server points at ``<publish_root>/current``; the symlink swap is atomic so
readers never see a half-copied tree. Old releases beyond ``--keep`` are pruned.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
DEFAULT_PUBLISH_ROOT = PROJECT_ROOT / "published"
SKIP_NAMES = {".DS_Store", "templates", "_kit"}


def git_short_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.strip()
        return out or "nogit"
    except Exception:
        return "nogit"


def copy_site(src: Path, dest: Path) -> None:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {n for n in names if n in SKIP_NAMES}

    shutil.copytree(src, dest, symlinks=False, ignore=ignore)


def swap_symlink(link: Path, target: Path) -> None:
    tmp = link.with_name(link.name + ".tmp")
    if tmp.is_symlink() or tmp.exists():
        tmp.unlink()
    os.symlink(os.path.relpath(target, link.parent), tmp)
    os.replace(tmp, link)


def prune(releases: Path, keep: int, protect: set[Path]) -> list[Path]:
    removed: list[Path] = []
    entries = sorted((p for p in releases.iterdir() if p.is_dir()), key=lambda p: p.name)
    for old in entries[:-keep] if keep > 0 else []:
        if old.resolve() in protect:
            continue
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--publish-root", type=Path, default=Path(os.environ.get("MAYOR_PUBLISH_ROOT", DEFAULT_PUBLISH_ROOT)))
    parser.add_argument("--keep", type=int, default=5, help="How many releases to keep (default 5).")
    parser.add_argument("--site", type=Path, default=SITE_ROOT)
    args = parser.parse_args()

    site = args.site.resolve()
    if not (site / "index.html").exists():
        print(f"ERROR: {site} has no index.html; build the site first.", file=sys.stderr)
        return 1

    root: Path = args.publish_root.resolve()
    releases = root / "releases"
    releases.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    release = releases / f"{stamp}-{git_short_sha()}"
    copy_site(site, release)

    current = root / "current"
    previous = root / "previous"
    old_current = current.resolve() if current.is_symlink() else None
    if old_current is not None and old_current != release:
        swap_symlink(previous, old_current)
    swap_symlink(current, release)

    protect = {release.resolve()}
    if previous.is_symlink():
        protect.add(previous.resolve())
    removed = prune(releases, args.keep, protect)

    print(f"Published {site} -> {release} (current={current}, previous={previous.resolve() if previous.is_symlink() else None}, pruned={len(removed)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
