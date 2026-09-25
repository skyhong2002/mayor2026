"""`/search/` — client-side full-text search over every roster post.

Writes site/data/search-index.json: compact records, newest first
  {id, c candidateId, p platform, t epoch, x text[:300], i imageUrl|null,
   a imageAspect, o topics, n intent type, u url, r intent confidence}
pages/search.js expands them back to post-like objects for MO.postHTML.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from . import shell as S

INDEX_PATH = S.SITE_ROOT / "data" / "search-index.json"
TEXT_LIMIT = 300
PLATFORMS = ("facebook", "instagram", "threads", "youtube", "x", "website", "podcast")


def _record(post: Dict[str, Any]) -> Dict[str, Any]:
    intent = post.get("postingIntent") if isinstance(post.get("postingIntent"), dict) else {}
    conf = intent.get("confidence")
    text = (post.get("text") or "").strip()
    return {
        "id": post.get("id"),
        "c": post.get("candidateId"),
        "p": post.get("platform") or "website",
        "t": S.epoch(post.get("postedAt")),
        "x": text[:TEXT_LIMIT] + ("…" if len(text) > TEXT_LIMIT else ""),
        "i": post.get("imageUrl") or None,
        "a": post.get("imageAspect"),
        "o": [t for t in (post.get("topics") or []) if t],
        "n": intent.get("type") or None,
        "u": post.get("url") or "",
        "r": round(float(conf), 2) if isinstance(conf, (int, float)) else None,
    }


def write_index(data) -> int:
    records = [_record(p) for p in data.all_posts()]
    cands = [{k: c.get(k) for k in ("id", "name", "city", "party", "avatarUrl")} for c in data.candidates]
    payload = {"version": 1, "generatedAt": data.generated_at.isoformat(), "count": len(records),
               "candidates": cands, "posts": records}
    S.write_text(INDEX_PATH, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return len(records)


def _chip_row(label: str, key: str, items) -> str:
    chips = "".join(S.render_chip(text, pressed=False, city=city, icon_name=ic,
                                  attrs={"data-fk": key, "data-fv": value})
                    for value, text, city, ic in items)
    return (f'<div class="filter-row"><span class="filter-label">{S.esc(label)}</span>'
            f'<div class="chips">{chips}</div></div>')


def render(data) -> None:
    count = write_index(data)
    city_row = _chip_row("城市", "city", [(c, S.city_label(c), c, None) for c in S.CITY_ORDER])
    plat_row = _chip_row("平台", "platform", [(p, S.PLATFORM_LABELS.get(p, p), None, p) for p in PLATFORMS])
    intent_seg = (
        '<div class="filter-row"><span class="filter-label">動機</span>'
        '<div class="seg" role="group" aria-label="發文動機">'
        '<button type="button" data-fk="intent" data-fv="" aria-pressed="true">全部</button>'
        '<button type="button" data-fk="intent" data-fv="self_initiated" aria-pressed="false">主動發文</button>'
        '<button type="button" data-fk="intent" data-fv="responsive" aria-pressed="false">回應他方觀點</button>'
        "</div></div>"
    )
    body = (
        S.page_head("搜尋", f"在 {count:,} 則候選人官方公開發文中搜尋內文與候選人姓名。結果依時間由新到舊排列。")
        + '<form class="search-box" role="search" action="/search/" method="get">'
          '<label class="sr-only" for="search-q">搜尋貼文</label>'
          f'<span class="search-icon" aria-hidden="true">{S.icon("search")}</span>'
          '<input class="input" id="search-q" name="q" type="search" autocomplete="off" enterkeyhint="search" '
          'placeholder="輸入關鍵字，例如：捷運、社宅、長照" autofocus>'
          "</form>"
        + f'<div class="search-filters">{city_row}{plat_row}{intent_seg}</div>'
        + '<p class="search-count" id="search-count" role="status" aria-live="polite"></p>'
        + '<div class="feed search-results" id="search-results">'
        + S.render_empty("輸入關鍵字開始搜尋", "可以輸入多個關鍵字（以空白分隔），也可以只用城市、平台篩選瀏覽最新貼文。")
        + "</div>"
        + '<div class="feed-more" id="search-more" hidden><button class="btn btn-sm" type="button">顯示更多結果</button></div>'
        + '<noscript><div class="notice" data-tone="warn"><p>搜尋需要啟用 JavaScript。'
          '也可以到<a href="/source/">候選人目錄</a>瀏覽各候選人的完整貼文。</p></div></noscript>'
        + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(data.generated_at.isoformat(), True))}（GMT+8）・'
          "搜尋只比對每則貼文的前 300 字；請點原文查看完整內容。</p>"
    )
    html = S.layout("search", "搜尋", "搜尋 2026 六都市長候選人在官方帳號的公開發文，依城市、平台與發文動機篩選。",
                    "/search/", body, extra_css=["pages/search.css"], extra_js=["pages/search.js"])
    S.write_page("/search/", html)
