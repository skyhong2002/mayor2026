"""Shared helpers for fetch adapters and the feed watchdog."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOCIAL_SOURCES_JSON = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
INBOX_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
CANDIDATES_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
ERRORS_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_feed_errors.jsonl"

HTML_TAG_RE = re.compile(r"<[^>]+>")


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9一-鿿]+", "-", value).strip("-").lower()
    return value or "candidate"


def candidate_id_from_row(row: dict[str, str]) -> str:
    city = (row.get("city") or "").strip()
    public_id = (row.get("public_id") or "").strip()
    name = (row.get("candidate_name_en") or "").strip() or (row.get("candidate_name") or "").strip()
    return f"{city}-{public_id}-{slugify(name)}"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def append_jsonl_dedup(path: Path, new_rows: Iterable[dict[str, Any]], *, key: str = "id") -> int:
    """Append rows whose `key` value isn't already present in the file. Returns count appended."""
    existing_ids = {row.get(key) for row in read_jsonl(path)}
    to_append = [row for row in new_rows if row.get(key) not in existing_ids]
    if not to_append:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in to_append:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return len(to_append)


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub("", text)
    return text.strip()


def load_sources(platforms: set[str] | None = None) -> list[dict[str, Any]]:
    config = load_json(SOCIAL_SOURCES_JSON, {"sources": []})
    sources = config.get("sources", [])
    if platforms:
        sources = [s for s in sources if s.get("platform") in platforms]
    return [s for s in sources if s.get("enabled", True)]


def record_error(source_id: str, message: str) -> None:
    append_jsonl_dedup(
        ERRORS_JSONL,
        [
            {
                "id": f"{source_id}:{utc_now_iso()}",
                "source_id": source_id,
                "message": message,
                "recorded_at": utc_now_iso(),
            }
        ],
    )
    print(f"feed_common: error for {source_id}: {message}")
