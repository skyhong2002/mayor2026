"""Small stdlib-only helpers shared by official-site adapters."""

from __future__ import annotations

import datetime as dt
import email.utils
import html
from html.parser import HTMLParser
import re
import urllib.request
import xml.etree.ElementTree as ET


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "mayor2026-official-site-fetcher/1.0"
)
TAIPEI = dt.timezone(dt.timedelta(hours=8))


def request_text(url: str, *, timeout: float = 20.0) -> tuple[str, str]:
    """Return decoded response text and the final URL; HTTP/network errors raise."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            text = raw.decode("utf-8", errors="replace")
        return text, response.geturl()


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


def taipei_iso(year: int, month: int, day: int) -> str:
    return dt.datetime(year, month, day, tzinfo=TAIPEI).isoformat()


def parse_date(value: str) -> str:
    """Convert common site/RSS dates to ISO 8601, normalised to Taiwan time."""
    value = " ".join((value or "").split())
    match = re.search(r"\b(20\d{2})[./-](\d{1,2})[./-](\d{1,2})\b", value)
    if match:
        return taipei_iso(*(int(part) for part in match.groups()))
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TAIPEI)
    return parsed.astimezone(TAIPEI).isoformat()


def _tag_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def _first_text(element: ET.Element, names: set[str]) -> str:
    for child in element.iter():
        if _tag_name(child) in names and child.text:
            return child.text.strip()
    return ""


def fetch_feed(url: str, *, limit: int = 10) -> list[dict]:
    """Parse an RSS or Atom feed into the official-site adapter contract."""
    xml_text, _ = request_text(url)
    root = ET.fromstring(xml_text)
    entries = [node for node in root.iter() if _tag_name(node) in {"item", "entry"}]
    rows: list[dict] = []
    for entry in entries:
        title = _first_text(entry, {"title"})
        summary = _first_text(entry, {"description", "summary", "encoded", "content"})
        article_url = ""
        media: list[str] = []
        for child in entry.iter():
            name = _tag_name(child)
            if name == "link":
                candidate = (child.get("href") or child.text or "").strip()
                rel = (child.get("rel") or "alternate").lower()
                if candidate and rel == "alternate" and not article_url:
                    article_url = candidate
            if name in {"content", "thumbnail", "enclosure"}:
                candidate = (child.get("url") or child.get("href") or "").strip()
                media_type = (child.get("type") or "").lower()
                if candidate and (name != "enclosure" or media_type.startswith("image/")):
                    if candidate not in media:
                        media.append(candidate)
        guid = _first_text(entry, {"guid", "id"})
        posted_at = parse_date(_first_text(entry, {"pubdate", "published", "updated", "date"}))
        text = " ".join(part for part in (plain_text(title), plain_text(summary)) if part)
        text = " ".join(text.split())
        post_id = article_url or guid
        if not post_id:
            continue
        rows.append(
            {
                "post_id": post_id,
                "url": article_url or url,
                "posted_at": posted_at,
                "text": text,
                "media": media,
            }
        )
    rows.sort(key=lambda row: row["posted_at"], reverse=True)
    return rows[:limit]


def attrs_dict(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    return {key: value or "" for key, value in attrs}


def classes(attrs: dict[str, str]) -> set[str]:
    return set(attrs.get("class", "").split())


def clean_parts(parts: list[str], *, drop: set[str] | None = None) -> str:
    dropped = drop or set()
    values = []
    for part in parts:
        value = html.unescape(" ".join(part.split()))
        if value and value not in dropped:
            values.append(value)
    return " ".join(values)
