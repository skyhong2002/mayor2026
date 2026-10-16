#!/usr/bin/env python3
"""Fetch recent YouTube uploads for watched candidates via yt-dlp.

Working skeleton: if `yt-dlp` is installed and on PATH, this fetches real
metadata for each candidate's YouTube channel. If yt-dlp is missing, it
prints a skip message and exits 0 (non-fatal) so the rest of the pipeline
still runs.

  TODO: pin a yt-dlp version in the Hsinchu machine's environment; YouTube
  regularly breaks older extractor versions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
from typing import Any, Optional

import feed_common
import source_status

YTDLP_BIN = shutil.which("yt-dlp")
CHANNEL_FETCH_TIMEOUT_SECS = 120
VIDEO_FETCH_TIMEOUT_SECS = 60

# Per-video date-lookup outcomes worth remembering live in the shared fetch
# state file under this key, so deleted/private videos and not-yet-premiered
# ones stop costing a yt-dlp call on every run.
LOOKUP_STATE_KEY = "youtube_videos"
# Matched against yt-dlp's ERROR: lines only. Bot checks and YouTube's
# rate-limit wording ("Video unavailable. This content isn't available, try
# again later") stay transient and keep retrying every run.
TRANSIENT_LOOKUP_ERROR_RE = re.compile(r"try again later|sign in to confirm|not a bot|rate.?limit|\b429\b", re.I)
PERMANENT_LOOKUP_ERROR_RE = re.compile(
    r"video unavailable|this video is (?:unavailable|not available|no longer available)|private video"
    r"|removed by the uploader",
    re.I,
)
UPCOMING_STARTING_RE = re.compile(r"premiere will begin shortly|will begin in a few moments", re.I)
UPCOMING_IN_RE = re.compile(r"(?:premieres|will begin) in (\d+) (minute|hour|day)s?\b", re.I)
UPCOMING_RE = re.compile(r"premiere|live event will begin|upcoming", re.I)
UPCOMING_UNKNOWN_BACKOFF = dt.timedelta(hours=24)


def fetch_channel_videos(url: str, *, limit: int) -> list[dict[str, Any]]:
    if not YTDLP_BIN:
        return []
    command = [
        YTDLP_BIN,
        "--flat-playlist",
        "--dump-json",
        "--playlist-end",
        str(limit),
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=CHANNEL_FETCH_TIMEOUT_SECS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp exited non-zero")
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def fetch_video_posted_at(video_id: str) -> str:
    """Flat-playlist listings carry no upload date, so new videos get one
    extra per-video metadata call. Returns "" if the date can't be found."""
    command = [
        YTDLP_BIN,
        "--skip-download",
        "--no-playlist",
        "--dump-json",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=VIDEO_FETCH_TIMEOUT_SECS)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp exited non-zero")
    info = json.loads(result.stdout)
    timestamp = info.get("release_timestamp") or info.get("timestamp")
    if timestamp:
        return dt.datetime.fromtimestamp(int(timestamp), tz=dt.timezone.utc).isoformat(timespec="seconds")
    upload_date = str(info.get("upload_date") or "")
    if len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T00:00:00+00:00"
    return ""


def classify_lookup_error(error: object, *, now: dt.datetime) -> Optional[dict[str, str]]:
    """Return the state entry to remember for a failed date lookup, or None
    when the failure is transient (timeouts, bot checks, rate limits, unknown
    errors) and the next run should simply try again."""
    lines = [line.strip() for line in str(error).splitlines() if line.strip().startswith("ERROR:")]
    text = "\n".join(lines)
    if not text or TRANSIENT_LOOKUP_ERROR_RE.search(text):
        return None
    entry = {"error": source_status.safe_error(lines[-1]), "recorded_at": source_status.iso(now)}
    if PERMANENT_LOOKUP_ERROR_RE.search(text):
        return {**entry, "status": "unavailable"}
    if UPCOMING_STARTING_RE.search(text):
        return None  # The premiere is starting now; next run's lookup should succeed.
    match = UPCOMING_IN_RE.search(text)
    if match:
        delay = dt.timedelta(**{f"{match.group(2).lower()}s": int(match.group(1))})
    elif UPCOMING_RE.search(text):
        delay = UPCOMING_UNKNOWN_BACKOFF
    else:
        return None
    return {**entry, "status": "upcoming", "retry_after": source_status.iso(now + delay)}


def lookup_due(entry: Optional[dict[str, Any]], *, now: dt.datetime) -> bool:
    if not entry:
        return True
    if entry.get("status") == "unavailable":
        return False
    retry_after = source_status.parse_time(entry.get("retry_after"))
    return retry_after is None or retry_after <= now


def load_lookup_state() -> dict[str, dict[str, Any]]:
    return source_status.load_state().get(LOOKUP_STATE_KEY, {})


def save_lookup_state(changes: dict[str, Optional[dict[str, Any]]]) -> None:
    """Apply per-video changes in one locked write; None removes an entry."""
    if not changes:
        return
    with source_status.locked_state() as state:
        videos = state.setdefault(LOOKUP_STATE_KEY, {})
        for video_id in sorted(changes):
            entry = changes[video_id]
            if entry is None:
                videos.pop(video_id, None)
            else:
                videos[video_id] = entry


def normalize_entries(
    source: dict[str, Any],
    entries: list[dict[str, Any]],
    known_ids: set[str],
    lookup_changes: Optional[dict[str, Optional[dict[str, Any]]]] = None,
    *,
    now: Optional[dt.datetime] = None,
) -> list[dict[str, Any]]:
    """Failed date lookups worth remembering are added to `lookup_changes`
    (the caller saves them) so the backfill pass doesn't repeat them."""
    rows = []
    for entry in entries:
        video_id = entry.get("id")
        if not video_id:
            continue
        row_id = f"youtube:{video_id}"
        posted_at = ""
        if row_id not in known_ids:  # only new rows are worth the extra metadata call
            try:
                posted_at = fetch_video_posted_at(video_id)
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                print(f"youtube_ytdlp_fetcher: date lookup failed for {video_id}: {exc}")
                lookup = classify_lookup_error(exc, now=now or source_status.utc_now())
                if lookup and lookup_changes is not None:
                    lookup_changes[video_id] = lookup
        rows.append(
            {
                "id": row_id,
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": "youtube",
                "source_id": source["id"],
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                "posted_at": posted_at,
                "text": entry.get("title") or "",
                "media": [entry["thumbnails"][-1]["url"]] if entry.get("thumbnails") else [],
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


def backfill_missing_dates(*, limit: int, now: Optional[dt.datetime] = None) -> int:
    """Self-healing pass: fill posted_at on already-ingested YouTube rows
    whose per-video lookup failed (or predates this feature). Bounded per run
    so a scheduled tick never stalls on a long tail. Videos known to be gone
    are never looked up again, and upcoming premieres wait until they air."""
    inbox = feed_common.read_jsonl(feed_common.INBOX_JSONL)
    missing = [row for row in inbox if row.get("platform") == "youtube" and not row.get("posted_at")]
    if not missing or limit <= 0:
        return 0
    now = now or source_status.utc_now()
    known = load_lookup_state()
    missing_ids = {row["id"].removeprefix("youtube:") for row in missing}
    # Forget entries for rows that have a date now (or left the inbox).
    lookup_changes: dict[str, Optional[dict[str, Any]]] = {vid: None for vid in known if vid not in missing_ids}
    due = [row for row in missing if lookup_due(known.get(row["id"].removeprefix("youtube:")), now=now)]
    if len(due) < len(missing):
        print(
            f"youtube_ytdlp_fetcher: backfill skipping {len(missing) - len(due)} row(s) "
            "known unavailable or not yet premiered."
        )
    updates: dict[str, dict[str, Any]] = {}
    for row in due[:limit]:
        video_id = row["id"].removeprefix("youtube:")
        try:
            posted_at = fetch_video_posted_at(video_id)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            print(f"youtube_ytdlp_fetcher: backfill date lookup failed for {video_id}: {exc}")
            entry = classify_lookup_error(exc, now=now)
            if entry:
                lookup_changes[video_id] = entry
            continue
        if video_id in known:
            lookup_changes[video_id] = None
        if posted_at:
            updates[row["id"]] = {"posted_at": posted_at}
    save_lookup_state(lookup_changes)
    if not updates:
        return 0
    changed = feed_common.fill_jsonl_fields(feed_common.INBOX_JSONL, updates)
    feed_common.fill_jsonl_fields(feed_common.CANDIDATES_JSONL, updates)
    print(f"youtube_ytdlp_fetcher: backfilled posted_at on {changed} row(s) ({len(missing) - len(updates)} still missing).")
    return changed


def fetch_channel_profile(url: str) -> dict[str, str]:
    """Fetch a channel's display name and avatar URL (one extra yt-dlp call)."""
    command = [YTDLP_BIN, "--skip-download", "--playlist-items", "0", "--dump-single-json", url]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp exited non-zero")
    info = json.loads(result.stdout)
    avatar_url = ""
    for thumb in info.get("thumbnails") or []:
        if thumb.get("id") == "avatar_uncropped":
            avatar_url = thumb.get("url", "")
            break
    return {"display_name": info.get("channel") or info.get("title") or "", "avatar_url": avatar_url}


def update_source_profiles(sources: list[dict[str, Any]], names_from_entries: dict[str, str]) -> None:
    profiles = feed_common.load_json(feed_common.SOURCE_PROFILES_JSON, {})
    changed = False
    for source in sources:
        entry = profiles.setdefault(source["id"], {})
        entry.setdefault("candidate_id", source["candidate_id"])
        entry.setdefault("platform", "youtube")
        name = names_from_entries.get(source["id"], "")
        if name and entry.get("display_name") != name:
            entry["display_name"] = name
            changed = True
        if not entry.get("avatar_url"):
            try:
                profile = fetch_channel_profile(source["url"])
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                print(f"youtube_ytdlp_fetcher: profile fetch failed for {source['id']}: {exc}")
                continue
            if profile["display_name"] and not entry.get("display_name"):
                entry["display_name"] = profile["display_name"]
            if profile["avatar_url"]:
                entry["avatar_url"] = profile["avatar_url"]
            entry["updated_at"] = feed_common.utc_now_iso()
            changed = True
    if changed:
        feed_common.save_json_atomic(feed_common.SOURCE_PROFILES_JSON, profiles)
        print("youtube_ytdlp_fetcher: updated channel profiles in source_profiles.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backfill-limit", type=int, default=10, help="Max already-ingested rows to backfill posted_at for per run.")
    parser.add_argument("--backfill-only", action="store_true", help="Skip channel fetching; only backfill missing posted_at.")
    args = parser.parse_args()

    if not YTDLP_BIN:
        if not args.dry_run:
            for source in feed_common.load_sources(platforms={"youtube"}):
                source_status.record_fetch(source, ok=False, error="yt-dlp 未安裝或不在 PATH")
        print("youtube_ytdlp_fetcher: yt-dlp not found on PATH; skipping. Install with `pip install yt-dlp`.")
        return 0

    if args.backfill_only:
        backfill_missing_dates(limit=args.backfill_limit)
        return 0

    sources = feed_common.load_sources(platforms={"youtube"})
    if not sources:
        print("youtube_ytdlp_fetcher: no youtube sources configured; nothing to do.")
        return 0

    known_ids = {row.get("id") for row in feed_common.read_jsonl(feed_common.INBOX_JSONL)}
    all_rows: list[dict[str, Any]] = []
    appended = 0
    channel_names: dict[str, str] = {}
    lookup_changes: dict[str, Optional[dict[str, Any]]] = {}
    for source in sources:
        if not source_status.retry_ready(source):
            continue
        try:
            entries = fetch_channel_videos(source["url"], limit=args.limit)
        except (RuntimeError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            if not args.dry_run:
                source_status.record_fetch(source, ok=False, error=exc)
                feed_common.record_error(source["id"], f"yt-dlp fetch failed: {source_status.safe_error(exc)}")
            continue
        for entry in entries:
            name = entry.get("channel") or entry.get("uploader")
            if name:
                channel_names[source["id"]] = name
                break
        rows = normalize_entries(source, entries, known_ids, lookup_changes)
        if not args.dry_run:
            appended += feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, rows)
            source_status.record_fetch(source, ok=True, items=len(rows))
        all_rows.extend(rows)
        print(f"youtube_ytdlp_fetcher: {source['id']} -> {len(rows)} item(s)")

    update_source_profiles(sources, channel_names)

    if args.dry_run:
        print(f"youtube_ytdlp_fetcher: dry-run, fetched {len(all_rows)} item(s), not writing.")
        return 0

    print(f"youtube_ytdlp_fetcher: appended {appended} new item(s).")
    save_lookup_state(lookup_changes)  # before backfill, so it skips what just failed
    backfill_missing_dates(limit=args.backfill_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
