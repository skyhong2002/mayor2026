#!/usr/bin/env python3
"""Export a stratified annotation queue or score completed human labels."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import feed_common

DEFAULT_PATH = feed_common.PROJECT_ROOT / "data" / "review" / "context-annotation-200.csv"
FIELDS = ["post_id", "candidate_id", "posted_at", "text", "predicted_trigger", "annotator_1", "annotator_2", "adjudicated_trigger", "notes"]


def export(path: Path, limit: int) -> None:
    rows = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    rows.sort(key=lambda row: ((row.get("trigger") or {}).get("type", ""), row.get("posted_at") or ""), reverse=True)
    # Round-robin over predicted classes creates a more useful QA sample than
    # simply taking the newest posts.
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault((row.get("trigger") or {}).get("type", "unclear"), []).append(row)
    sample = []
    while len(sample) < min(limit, len(rows)) and any(groups.values()):
        for key in sorted(groups):
            if groups[key] and len(sample) < limit:
                sample.append(groups[key].pop(0))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in sample:
            writer.writerow({"post_id": row["id"], "candidate_id": row["candidate_id"], "posted_at": row.get("posted_at", ""),
                             "text": row.get("text", ""), "predicted_trigger": (row.get("trigger") or {}).get("type", "unclear")})
    print(f"context_annotation: exported {len(sample)} rows to {path}")


def score(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    completed = [row for row in rows if row.get("adjudicated_trigger")]
    if not completed:
        print("context_annotation: no adjudicated labels yet")
        return 2
    correct = sum(row["predicted_trigger"] == row["adjudicated_trigger"] for row in completed)
    response = [row for row in completed if row["predicted_trigger"] == "direct_response"]
    response_precision = sum(row["adjudicated_trigger"] == "direct_response" for row in response) / len(response) if response else 1.0
    print(f"completed={len(completed)}/{len(rows)} accuracy={correct / len(completed):.1%} direct_response_precision={response_precision:.1%}")
    return 0 if len(completed) >= 200 and correct / len(completed) >= .8 and response_precision >= .9 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["export", "score"])
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    if args.command == "export":
        export(args.path, args.limit)
        return 0
    return score(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
