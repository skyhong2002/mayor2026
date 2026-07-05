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
import json
import shutil
import subprocess
from typing import Any

import feed_common

YTDLP_BIN = shutil.which("yt-dlp")


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
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "yt-dlp exited non-zero")
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def normalize_entries(source: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in entries:
        video_id = entry.get("id")
        if not video_id:
            continue
        rows.append(
            {
                "id": f"youtube:{video_id}",
                "candidate_id": source["candidate_id"],
                "city": source["city"],
                "platform": "youtube",
                "source_id": source["id"],
                "url": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                "posted_at": "",  # flat-playlist mode doesn't return upload_date; needs a per-video lookup.
                "text": entry.get("title") or "",
                "media": [entry["thumbnails"][-1]["url"]] if entry.get("thumbnails") else [],
                "fetched_at": feed_common.utc_now_iso(),
            }
        )
    return rows


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
    args = parser.parse_args()

    if not YTDLP_BIN:
        print("youtube_ytdlp_fetcher: yt-dlp not found on PATH; skipping. Install with `pip install yt-dlp`.")
        return 0

    sources = feed_common.load_sources(platforms={"youtube"})
    if not sources:
        print("youtube_ytdlp_fetcher: no youtube sources configured; nothing to do.")
        return 0

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
        rows = normalize_entries(source, entries)
        all_rows.extend(rows)
        print(f"youtube_ytdlp_fetcher: {source['id']} -> {len(rows)} item(s)")

    update_source_profiles(sources, channel_names)

    if args.dry_run:
        print(f"youtube_ytdlp_fetcher: dry-run, fetched {len(all_rows)} item(s), not writing.")
        return 0

    appended = feed_common.append_jsonl_dedup(feed_common.INBOX_JSONL, all_rows)
    print(f"youtube_ytdlp_fetcher: appended {appended} new item(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
