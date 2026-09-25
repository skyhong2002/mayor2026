"""Single cached entry point to the public JSON under site/api/.

    from render import data as data_mod
    data = data_mod.load()
    data.candidates          # roster list (api/candidates.json order)
    data.by_id["shen-poyang"]
    data.posts_for("shen-poyang")   # lazy, newest first
    data.all_posts()         # roster-only, newest first (memoised)

Everything derived from spectrum / topic-index is filtered to the roster.
"""

from __future__ import annotations

import datetime as dt
from functools import cached_property
from typing import Any

from .shell import CITY_LABELS, CITY_ORDER, SITE_ROOT, asset_abs, epoch, read_json  # noqa: F401

API_DIR = SITE_ROOT / "api"


class Data:
    def __init__(self) -> None:
        payload = read_json(API_DIR / "candidates.json", {}) or {}
        self.candidates: list[dict[str, Any]] = list(payload.get("candidates") or [])
        self.by_id: dict[str, dict[str, Any]] = {c["id"]: c for c in self.candidates}
        self.roster: set[str] = set(self.by_id)
        self._posts: dict[str, list[dict[str, Any]]] = {}
        self._all: list[dict[str, Any]] | None = None

    # -- roster helpers --------------------------------------------------
    @cached_property
    def cities(self) -> list[dict[str, Any]]:
        """[{id,label,candidateIds}] in fixed CITY_ORDER (roster-filtered)."""
        raw = (read_json(API_DIR / "cities.json", {}) or {}).get("cities") or []
        by_city = {c.get("id"): c for c in raw}
        out = []
        for slug in CITY_ORDER:
            entry = by_city.get(slug) or {"id": slug, "label": CITY_LABELS[slug], "candidateIds": []}
            ids = [i for i in entry.get("candidateIds") or [] if i in self.roster]
            if not ids:
                ids = [c["id"] for c in self.candidates if c.get("city") == slug]
            out.append({**entry, "candidateIds": ids})
        return out

    def candidates_in(self, city: str) -> list[dict[str, Any]]:
        return [c for c in self.candidates if c.get("city") == city]

    @cached_property
    def sources(self) -> list[dict[str, Any]]:
        """api/sources.json → candidates with ``accounts`` (roster-filtered)."""
        raw = (read_json(API_DIR / "sources.json", {}) or {}).get("sources") or []
        return [s for s in raw if s.get("id") in self.roster]

    @cached_property
    def sources_by_id(self) -> dict[str, dict[str, Any]]:
        return {s["id"]: s for s in self.sources}

    # -- posts -------------------------------------------------------------
    def posts_for(self, candidate_id: str) -> list[dict[str, Any]]:
        """Posts of one candidate, newest first (by parsed timestamp)."""
        if candidate_id not in self._posts:
            raw = (read_json(API_DIR / "posts" / f"{candidate_id}.json", {}) or {}).get("posts") or []
            self._posts[candidate_id] = sorted(raw, key=lambda p: epoch(p.get("postedAt")), reverse=True)
        return self._posts[candidate_id]

    def all_posts(self) -> list[dict[str, Any]]:
        """Every roster post merged, newest first. Undated posts sort last."""
        if self._all is None:
            merged = [p for cid in self.by_id for p in self.posts_for(cid)]
            self._all = sorted(merged, key=lambda p: epoch(p.get("postedAt")), reverse=True)
        return self._all

    @cached_property
    def latest(self) -> list[dict[str, Any]]:
        raw = (read_json(API_DIR / "latest.json", {}) or {}).get("posts") or []
        return [p for p in raw if p.get("candidateId") in self.roster]

    # -- derived datasets (roster-filtered) ----------------------------------
    @cached_property
    def spectrum(self) -> list[dict[str, Any]]:
        raw = (read_json(API_DIR / "spectrum.json", {}) or {}).get("candidates") or []
        return [r for r in raw if r.get("candidateId") in self.roster]

    @cached_property
    def topic_index(self) -> list[dict[str, Any]]:
        raw = (read_json(API_DIR / "topic-index.json", {}) or {}).get("posts") or []
        return [r for r in raw if r.get("candidateId") in self.roster]

    @cached_property
    def topic_details(self) -> dict[str, Any]:
        raw = read_json(API_DIR / "topic-details.json", {}) or {}
        topics = {
            topic: {cid: kws for cid, kws in (per or {}).items() if cid in self.roster}
            for topic, per in (raw.get("topics") or {}).items()
        }
        return {**raw, "topics": topics}

    @cached_property
    def policy_match(self) -> dict[str, Any]:
        return read_json(API_DIR / "policy-match.json", {}) or {}

    @cached_property
    def qualitative(self) -> dict[str, Any]:
        return read_json(API_DIR / "qualitative-summary.json", {}) or {}

    @cached_property
    def status(self) -> dict[str, Any] | None:
        return read_json(API_DIR / "status.json", None)

    @cached_property
    def generated_at(self) -> dt.datetime:
        """Snapshot time: status.generatedAt, else newest post, else now (UTC-aware)."""
        from .shell import parse_ts
        stamp = parse_ts((self.status or {}).get("generatedAt"))
        if stamp:
            return stamp
        for post in self.all_posts():
            stamp = parse_ts(post.get("postedAt"))
            if stamp:
                return stamp
        return dt.datetime.now(dt.timezone.utc)

    # -- render_post context ---------------------------------------------------
    def post_ctx(self, **opts: Any) -> dict[str, Any]:
        """Context dict for shell.render_post(); opts: show_city, show_json."""
        return {"by_id": self.by_id, **opts}


_CACHE: Data | None = None


def load(refresh: bool = False) -> Data:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = Data()
    return _CACHE
