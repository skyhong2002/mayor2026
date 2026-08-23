"""Adapter for the article cards in chiao.tw's 巧觀點 listing."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from urllib.parse import urljoin

from ._common import attrs_dict, classes, clean_parts, parse_date, request_text


class _Cards(HTMLParser):
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.current: dict | None = None
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = attrs_dict(attrs_list)
        if tag == "article" and "card" in classes(attrs) and self.current is None:
            self.current = {"href": "", "parts": [], "media": []}
            self.depth = 1
            return
        if self.current is None:
            return
        if tag not in self._VOID:
            self.depth += 1
        href = attrs.get("href", "")
        if tag == "a" and "/chiao_view/" in href and not self.current["href"]:
            self.current["href"] = href
        if tag == "img" and attrs.get("src"):
            self.current["media"].append(attrs["src"])
        if tag == "source" and attrs.get("srcset"):
            self.current["media"].append(attrs["srcset"].split()[0])

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


def fetch(url: str) -> list[dict]:
    listing_url = urljoin(url, "/chiao-view/")
    body, _ = request_text(listing_url)
    parser = _Cards()
    parser.feed(body)
    rows = []
    seen: set[str] = set()
    for card in parser.rows:
        if not card["href"]:
            continue
        article_url = urljoin(listing_url, card["href"])
        if article_url in seen:
            continue
        seen.add(article_url)
        text = clean_parts(card["parts"], drop={"閱讀"})
        date_match = re.search(r"\b20\d{2}\.\d{1,2}\.\d{1,2}\b", text)
        rows.append(
            {
                "post_id": article_url,
                "url": article_url,
                "posted_at": parse_date(date_match.group(0) if date_match else ""),
                "text": text,
                "media": list(dict.fromkeys(card["media"])),
            }
        )
    rows.sort(key=lambda row: row["posted_at"], reverse=True)
    return rows[:10]
