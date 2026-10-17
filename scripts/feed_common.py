"""Shared helpers for fetch adapters and the feed watchdog."""

from __future__ import annotations

import csv
import datetime as dt
import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")
SOCIAL_SOURCES_JSON = PROJECT_ROOT / "data" / "feeds" / "social_sources.json"
INBOX_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_feed_inbox.jsonl"
CANDIDATES_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_candidates.jsonl"
ERRORS_JSONL = PROJECT_ROOT / "data" / "feeds" / "social_feed_errors.jsonl"
SOURCE_PROFILES_JSON = PROJECT_ROOT / "data" / "feeds" / "source_profiles.json"
CANDIDATES_CSV = PROJECT_ROOT / "data" / "sources" / "candidates.csv"
ACCOUNTS_CSV = PROJECT_ROOT / "data" / "sources" / "watchlist_accounts.csv"

HTML_TAG_RE = re.compile(r"<[^>]+>")

CITY_LABELS = {
    "taipei": "臺北市",
    "new-taipei": "新北市",
    "taoyuan": "桃園市",
    "taichung": "臺中市",
    "tainan": "臺南市",
    "kaohsiung": "高雄市",
}
VALID_CITIES = set(CITY_LABELS)

# Lower rank = preferred when a candidate has more than one account on the
# same platform (e.g. a campaign FB page and a personal FB profile).
ACCOUNT_ROLE_RANK = {"campaign": 0, "incumbent": 0, "personal": 1, "affiliated": 2, "party": 3}
VERIFICATION_RANK = {"first_party": 0, "cross_ref": 1, "unverified": 2}


def account_sort_key(account: dict[str, Any]) -> tuple[int, int]:
    return (
        ACCOUNT_ROLE_RANK.get(account.get("account_role", ""), 3),
        VERIFICATION_RANK.get(account.get("verification", ""), 3),
    )


def clean(value: str | None) -> str:
    return (value or "").strip()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_candidates() -> list[dict[str, str]]:
    candidates = []
    for row in read_csv_rows(CANDIDATES_CSV):
        city = clean(row.get("city"))
        if city not in VALID_CITIES:
            print(f"feed_common: skipping candidate row with unknown city {city!r} (candidate_id={row.get('candidate_id')!r})")
            continue
        candidates.append(
            {
                "candidate_id": clean(row.get("candidate_id")),
                "name": clean(row.get("name")),
                "city": city,
                "party": clean(row.get("party")),
            }
        )
    return candidates


def load_accounts() -> list[dict[str, Any]]:
    accounts = []
    for row in read_csv_rows(ACCOUNTS_CSV):
        url = clean(row.get("url"))
        active = clean(row.get("active")).lower() in {"true", "1", "yes"}
        if not url or not active:
            continue
        accounts.append({key: clean(value) for key, value in row.items()})
    return accounts


def accounts_by_candidate(accounts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for account in accounts:
        grouped.setdefault(account["candidate_id"], []).append(account)
    return grouped


def best_accounts_per_platform(accounts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pick the single best account per platform for a candidate's link list."""
    by_platform: dict[str, list[dict[str, Any]]] = {}
    for account in accounts:
        by_platform.setdefault(account["platform"], []).append(account)
    return {platform: sorted(rows, key=account_sort_key)[0] for platform, rows in by_platform.items()}


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


@contextmanager
def jsonl_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]:
    """Coordinate readers and writers on a stable inode, even after a replace.

    Keep the sidecar in place: unlinking it would let two processes lock
    different inodes for the same feed. flock releases automatically on exit.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _read_jsonl_unlocked(path: Path) -> list[dict[str, Any]]:
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with jsonl_lock(path, exclusive=False):
        return _read_jsonl_unlocked(path)


def read_classified_candidates() -> list[dict[str, Any]]:
    """Candidate posts that classify_context has finished with.

    Text-less posts are left unclassified on purpose (nothing to classify) and
    must stay out of every public output and count.
    """
    return [row for row in read_jsonl(CANDIDATES_JSONL) if row.get("classification")]


def append_jsonl_dedup(path: Path, new_rows: Iterable[dict[str, Any]], *, key: str = "id") -> int:
    """Append each new ID once, including duplicates in this batch.

    The locked read/dedup/append transaction prevents overlapping fetchers
    from appending the same ID. Existing bytes and row order are untouched;
    the first occurrence wins. Encode the whole batch before writing so a
    bad row or failing iterator cannot leave a partially appended batch.
    """
    with jsonl_lock(path):
        seen = {row.get(key) for row in _read_jsonl_unlocked(path)}
        encoded = []
        for row in new_rows:
            row_id = row.get(key)
            if row_id in seen:
                continue
            encoded.append(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            seen.add(row_id)
        if not encoded:
            return 0
        # Older snapshots may lack a final newline. Add a separator without
        # rewriting that historical row or joining two JSON documents.
        separator = b""
        if path.exists() and path.stat().st_size:
            with path.open("rb") as existing:
                existing.seek(-1, os.SEEK_END)
                if existing.read(1) != b"\n":
                    separator = b"\n"
        payload = separator + "".join(encoded).encode("utf-8")
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        return len(encoded)


def _replace_jsonl_unlocked(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Publish an existing metadata update while holding jsonl_lock(path)."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fill_jsonl_fields(path: Path, updates: dict[str, dict[str, Any]], *, key: str = "id") -> int:
    """Fill in missing metadata fields on existing rows, atomically.

    Narrow exception to the append-only rule for the feed JSONLs: rows are
    never added, removed, or reordered, and a field is only written when the
    row's current value is empty/absent — used to backfill `posted_at` on
    YouTube rows fetched before per-video date lookup existed. Returns the
    number of rows changed.
    """
    with jsonl_lock(path):
        rows = _read_jsonl_unlocked(path)
        changed = 0
        for row in rows:
            fields = updates.get(row.get(key))
            if not fields:
                continue
            row_changed = False
            for field, value in fields.items():
                if value and not row.get(field):
                    row[field] = value
                    row_changed = True
            changed += row_changed
        if changed:
            _replace_jsonl_unlocked(path, rows)
        return changed


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
