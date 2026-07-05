#!/usr/bin/env python3
"""Validate generated public outputs before publishing."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = PROJECT_ROOT / "site"
API_DIR = SITE_ROOT / "api"
FEEDS_DIR = SITE_ROOT / "feeds"

REQUIRED_FILES = [
    API_DIR / "candidates.json",
    API_DIR / "cities.json",
    API_DIR / "latest.json",
    API_DIR / "spectrum.json",
    API_DIR / "sources.json",
    FEEDS_DIR / "updates.xml",
    SITE_ROOT / "index.html",
    SITE_ROOT / "source" / "index.html",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required output: {path.relative_to(PROJECT_ROOT)}")


def validate_json_files(errors: list[str]) -> None:
    for path in sorted(API_DIR.rglob("*.json")):
        try:
            read_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {path.relative_to(PROJECT_ROOT)}:{exc.lineno}:{exc.colno}: {exc.msg}")


def validate_candidate_pages_exist(errors: list[str]) -> None:
    candidates_path = API_DIR / "candidates.json"
    if not candidates_path.exists():
        return
    try:
        candidates = read_json(candidates_path).get("candidates", [])
    except json.JSONDecodeError:
        return
    for candidate in candidates:
        candidate_id = candidate.get("id")
        post_json = API_DIR / "posts" / f"{candidate_id}.json"
        if not post_json.exists():
            errors.append(f"missing posts JSON for candidate {candidate_id}: {post_json.relative_to(PROJECT_ROOT)}")
        html_page = SITE_ROOT / candidate.get("city", "") / candidate_id / "index.html"
        if not html_page.exists():
            errors.append(f"missing candidate page: {html_page.relative_to(PROJECT_ROOT)}")


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    validate_json_files(errors)
    validate_candidate_pages_exist(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Public outputs validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
