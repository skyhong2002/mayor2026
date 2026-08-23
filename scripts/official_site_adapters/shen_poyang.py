"""Adapter for the dated daily-interview cards on puma.taipei."""

from __future__ import annotations

import datetime as dt
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from ._common import TAIPEI, attrs_dict, classes, clean_parts, request_text, taipei_iso


class _VideoCards(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.current: dict | None = None
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = attrs_dict(attrs_list)
        if tag == "li" and "video-card" in classes(attrs) and self.current is None:
            self.current = {"href": "", "parts": [], "media": []}
            self.depth = 1
            return
        if self.current is None:
            return
        if tag not in self._VOID:
            self.depth += 1
        href = attrs.get("href", "")
        if tag == "a" and re.search(r"/videos/[^/?#]+", href) and not self.current["href"]:
            self.current["href"] = href
        if tag == "img" and attrs.get("src"):
            self.current["media"].append(attrs["src"])

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.current["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        self.depth -= 1
        if self.depth == 0:
            self.rows.append(self.current)
            self.current = None


def _date_from_title(text: str) -> str:
    match = re.search(r"(?:^|\s)(\d{2})(\d{2})受訪", text)
    if not match:
        return ""
    month, day = (int(value) for value in match.groups())
    today = dt.datetime.now(TAIPEI).date()
    year = today.year
    candidate = dt.date(year, month, day)
    if candidate > today + dt.timedelta(days=7):
        year -= 1
    return taipei_iso(year, month, day)


def fetch(url: str) -> list[dict]:
    listing_url = urljoin(url, "/videos")
    body, _ = request_text(listing_url)
    parser = _VideoCards()
    parser.feed(body)
    rows = []
    seen: set[str] = set()
    for card in parser.rows:
        article_url = urljoin(listing_url, card["href"])
        post_id = urlsplit(article_url).path.rstrip("/").rsplit("/", 1)[-1]
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        text = clean_parts(card["parts"], drop={"觀看影片"})
        rows.append(
            {
                "post_id": post_id,
                "url": article_url,
                "posted_at": _date_from_title(text),
                "text": text,
                "media": list(dict.fromkeys(card["media"])),
            }
        )
    return rows[:10]
