#!/usr/bin/env python3
"""Cache post images and candidate avatars as local WebP files.

Remote CDN URLs (especially fbcdn) are signed and expire within weeks, so the
pipeline snapshots the first image of every post into
`site/assets/feed-images/` and every candidate avatar into
`site/assets/source-avatars/`, both as WebP named by the SHA-256 of the
remote URL (first 20 hex chars) — the same convention the Harmonica-in-Taiwan
project uses. Lookup maps live under `state/` so already-cached URLs are
never re-downloaded.
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

import feed_common

FEED_IMAGES_DIR = feed_common.PROJECT_ROOT / "site" / "assets" / "feed-images"
AVATARS_DIR = feed_common.PROJECT_ROOT / "site" / "assets" / "source-avatars"
IMAGE_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "feed_image_cache.json"
AVATAR_CACHE_JSON = feed_common.PROJECT_ROOT / "state" / "source_avatar_cache.json"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
REQUEST_TIMEOUT_SECS = 20
FEED_IMAGE_MAX_WIDTH = 1200
AVATAR_SIZE = 320
WEBP_QUALITY = 82


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECS) as response:
        return response.read()


def to_webp(raw: bytes, *, max_width: int, square: bool = False) -> tuple[bytes, float]:
    """Convert image bytes to WebP; returns (bytes, aspect_ratio w/h)."""
    image = Image.open(io.BytesIO(raw))
    image = image.convert("RGB")
    if square:
        side = min(image.size)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    if image.width > max_width:
        image = image.resize((max_width, round(image.height * max_width / image.width)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue(), image.width / image.height


def cache_image(url: str, target_dir: Path, *, max_width: int, square: bool = False) -> dict[str, Any] | None:
    filename = f"{url_hash(url)}.webp"
    target = target_dir / filename
    if target.exists():
        with Image.open(target) as existing:
            return {"file": filename, "aspect": round(existing.width / existing.height, 4)}
    try:
        raw = download(url)
        webp, aspect = to_webp(raw, max_width=max_width, square=square)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        print(f"fetch_media_cache: failed {url[:90]}...: {exc}")
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(webp)
    return {"file": filename, "aspect": round(aspect, 4)}


def first_image_url(media: list[Any]) -> str:
    for entry in media:
        if isinstance(entry, str) and entry.startswith("http"):
            return entry
    return ""


def cache_post_images() -> None:
    cache = feed_common.load_json(IMAGE_CACHE_JSON, {})
    posts = feed_common.read_jsonl(feed_common.CANDIDATES_JSONL)
    fetched = 0
    for post in posts:
        post_id = post["id"]
        if post_id in cache:
            continue
        url = first_image_url(post.get("media") or [])
        if not url:
            continue
        result = cache_image(url, FEED_IMAGES_DIR, max_width=FEED_IMAGE_MAX_WIDTH)
        # Cache failures too (as null) so expired CDN URLs aren't retried every run.
        cache[post_id] = result
        if result:
            fetched += 1
    feed_common.save_json_atomic(IMAGE_CACHE_JSON, cache)
    total = sum(1 for value in cache.values() if value)
    print(f"fetch_media_cache: {fetched} new post image(s) cached ({total} total).")


def cache_avatars() -> None:
    """Cache one avatar per watched account (profiles are keyed by account id)."""
    profiles = feed_common.load_json(feed_common.SOURCE_PROFILES_JSON, {})
    cache = feed_common.load_json(AVATAR_CACHE_JSON, {})
    fetched = 0
    for account_id, profile in profiles.items():
        url = profile.get("avatar_url")
        if not url:
            continue
        cached = cache.get(account_id)
        if cached and cached.get("url") == url:
            continue
        result = cache_image(url, AVATARS_DIR, max_width=AVATAR_SIZE, square=True)
        if result:
            cache[account_id] = {"url": url, "file": result["file"]}
            fetched += 1
    feed_common.save_json_atomic(AVATAR_CACHE_JSON, cache)
    print(f"fetch_media_cache: {fetched} new avatar(s) cached ({len(cache)} total).")


def main() -> int:
    cache_post_images()
    cache_avatars()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
