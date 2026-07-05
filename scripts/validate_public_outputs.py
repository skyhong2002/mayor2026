#!/usr/bin/env python3
"""Validate generated public outputs before publishing.

Checks ported from Harmonica-in-Taiwan's validate_public_outputs.py:
required files exist, every generated JSON parses, referenced local assets
(post images, avatars) actually exist on disk, and counts stay consistent
across the API surfaces. Validation failure blocks publishing.
"""

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
    API_DIR / "status.json",
    FEEDS_DIR / "updates.xml",
    FEEDS_DIR / "updates.json",
    FEEDS_DIR / "index.html",
    SITE_ROOT / "index.html",
    SITE_ROOT / "source" / "index.html",
    SITE_ROOT / "status" / "index.html",
    SITE_ROOT / "spectrum" / "index.html",
    SITE_ROOT / "spectrum" / "topic" / "transport" / "index.html",
    API_DIR / "topic-index.json",
    API_DIR / "topic-details.json",
    SITE_ROOT / "sitemap.xml",
    SITE_ROOT / "robots.txt",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required_files(errors: list[str]) -> None:
    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required output: {path.relative_to(PROJECT_ROOT)}")


def validate_json_files(errors: list[str]) -> None:
    for path in sorted([*API_DIR.rglob("*.json"), *FEEDS_DIR.glob("*.json")]):
        try:
            read_json(path)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {path.relative_to(PROJECT_ROOT)}:{exc.lineno}:{exc.colno}: {exc.msg}")


def iter_asset_refs(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_asset_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_asset_refs(child)
    elif isinstance(value, str) and value.startswith("assets/"):
        yield value


def validate_asset_references(errors: list[str]) -> None:
    missing: dict[str, set[str]] = {}
    for path in sorted(API_DIR.rglob("*.json")):
        try:
            payload = read_json(path)
        except json.JSONDecodeError:
            continue
        for ref in iter_asset_refs(payload):
            if not (SITE_ROOT / ref).exists():
                missing.setdefault(ref, set()).add(str(path.relative_to(PROJECT_ROOT)))
    for ref, refs in sorted(missing.items()):
        listed = ", ".join(sorted(refs)[:5])
        extra = "" if len(refs) <= 5 else f", +{len(refs) - 5} more"
        errors.append(f"missing referenced asset: {ref} used by {listed}{extra}")


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
        for page in (
            API_DIR / "posts" / f"{candidate_id}.json",
            SITE_ROOT / candidate.get("city", "") / candidate_id / "index.html",
            SITE_ROOT / "source" / candidate_id / "index.html",
            FEEDS_DIR / f"{candidate_id}.xml",
        ):
            if not page.exists():
                errors.append(f"missing output for candidate {candidate_id}: {page.relative_to(PROJECT_ROOT)}")


def validate_count_consistency(errors: list[str]) -> None:
    try:
        candidates = read_json(API_DIR / "candidates.json")
        sources = read_json(API_DIR / "sources.json")
        status = read_json(API_DIR / "status.json")
    except (OSError, json.JSONDecodeError):
        return
    if candidates.get("count") != sources.get("count"):
        errors.append(
            f"count mismatch: candidates.json count={candidates.get('count')!r}, sources.json count={sources.get('count')!r}"
        )
    metrics = status.get("metrics") or {}
    if metrics.get("candidates") != candidates.get("count"):
        errors.append(
            f"count mismatch: status.metrics.candidates={metrics.get('candidates')!r}, candidates.json count={candidates.get('count')!r}"
        )
    total_posts = metrics.get("totalPosts")
    per_candidate_total = sum(c.get("postCount", 0) for c in candidates.get("candidates", []))
    if total_posts != per_candidate_total:
        errors.append(
            f"count mismatch: status.metrics.totalPosts={total_posts!r}, sum of candidate postCount={per_candidate_total!r}"
        )


def main() -> int:
    errors: list[str] = []
    validate_required_files(errors)
    validate_json_files(errors)
    validate_asset_references(errors)
    validate_candidate_pages_exist(errors)
    validate_count_consistency(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Public outputs validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
