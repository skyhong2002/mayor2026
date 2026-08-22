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
import shutil
import subprocess
from typing import Any

import feed_common

YTDLP_BIN = shutil.which("yt-dlp")
CHANNEL_FETCH_TIMEOUT_SECS = 120
VIDEO_FETCH_TIMEOUT_SECS = 60


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


def normalize_entries(source: dict[str, Any], entries: list[dict[str, Any]], known_ids: set[str]) -> list[dict[str, Any]]:
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


def backfill_missing_dates(*, limit: int) -> int:
    """Self-healing pass: fill posted_at on already-ingested YouTube rows
    whose per-video lookup failed (or predates this feature). Bounded per run
    so a scheduled tick never stalls on a long tail."""
    inbox = feed_common.read_jsonl(feed_common.INBOX_JSONL)
    missing = [row for row in inbox if row.get("platform") == "youtube" and not row.get("posted_at")]
    if not missing or limit <= 0:
        return 0
    updates: dict[str, dict[str, Any]] = {}
    for row in missing[:limit]:
        video_id = row["id"].removeprefix("youtube:")
        try:
            posted_at = fetch_video_posted_at(video_id)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            print(f"youtube_ytdlp_fetcher: backfill date lookup failed for {video_id}: {exc}")
            continue
        if posted_at:
            updates[row["id"]] = {"posted_at": posted_at}
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
    channel_names: dict[str, str] = {}
    for source in sources:
        try:
            entries = fetch_channel_videos(source["url"], limit=args.limit)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            feed_common.record_error(source["id"], f"yt-dlp fetch failed: {exc}")
            continue
        for entry in entries:
            name = entry.get("channel") or entry.get("uploader")
            if name:
                channel_names[source["id"]] = name
                break
        rows = normalize_entries(source, entries, known_ids)
        all_rows.extend(rows)
        print(f"youtube_ytdlp_fetcher: {source['id']} -> {len(rows)} item(s)")

    update_source_profiles(sources, channel_names)

    if args.dry_run:
        print(f"youtube_ytdlp_fetcher: dry-run, fetched {len(all_rows)} item(s), not writing.")
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, all_rows)
    print(f"youtube_ytdlp_fetcher: appended {appended} new item(s).")
    backfill_missing_dates(limit=args.backfill_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
