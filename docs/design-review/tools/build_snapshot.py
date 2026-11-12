#!/usr/bin/env python3
"""Render one code version of the site against the frozen data fixture.

  python3 docs/design-review/tools/build_snapshot.py SRC OUT [--fixture DIR]

SRC is a checkout (or `git archive` export) of the code to photograph; OUT is a
scratch directory that receives a copy of SRC's code plus the fixture's
generated JSON, then runs only the HTML renderers (generate_site_pages.py and
generate_seo_pages.py). The clock is pinned to the fixture's snapshot time so
server-rendered relative times never drift between rounds. Nothing is fetched,
classified, synced or published.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

NOW = "2026-11-10T22:30:00+00:00"  # 30 min after the data-branch snapshot (2026-11-11 06:30 Asia/Taipei)
SKIP = {".git", "site", "published", "state", "logs", "__pycache__", "node_modules"}

# Imported by the child interpreter: replace datetime.datetime with a subclass
# whose now()/utcnow() return the pinned instant, then run the script.
RUNNER = r'''
import datetime as _d, runpy, sys
_NOW = _d.datetime.fromisoformat(sys.argv[1])
class _Frozen(_d.datetime):
    @classmethod
    def now(cls, tz=None):
        v = _NOW if tz is None else _NOW.astimezone(tz)
        return cls(v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond, v.tzinfo)
    @classmethod
    def utcnow(cls):
        v = _NOW.astimezone(_d.timezone.utc)
        return cls(v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond)
_d.datetime = _Frozen
import time as _t
_t.time = lambda: _NOW.timestamp()
script = sys.argv[2]
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
sys.argv = [script] + sys.argv[3:]
runpy.run_path(script, run_name="__main__")
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--fixture", type=Path, default=Path("/tmp/mayor-review/fixture"))
    args = parser.parse_args()
    src, out = args.src.resolve(), args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in src.iterdir():
        if item.name in SKIP:
            continue
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, out / item.name)
    shutil.copytree(src / "site" / "assets", out / "site" / "assets",
                    ignore=shutil.ignore_patterns("feed-images", "source-avatars"))
    fixture_site = args.fixture / "site"
    for name in ("api", "feeds"):
        shutil.copytree(fixture_site / name, out / "site" / name)
    for name in ("feed-images", "source-avatars"):
        (out / "site" / "assets" / name).symlink_to(fixture_site / "assets" / name)
    for script in ("scripts/generate_site_pages.py", "scripts/generate_seo_pages.py"):
        subprocess.run([sys.executable, "-c", RUNNER, NOW, script], cwd=out, check=True)
    print(out / "site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
