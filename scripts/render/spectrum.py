"""/spectrum/ (議題光譜熱圖) and /spectrum/<slug>/ (單一議題跨候選人比較 + 貼文河道).

Owns site/spectrum/ (wiped before writing; the orchestrator adds the
/spectrum/topic/<slug>/ redirect stubs afterwards) and site/data/topic/.

The heatmap maths mirrors site/assets/pages/spectrum.js ``compute()`` exactly:
per candidate, sum topicScores of every post that passes the range / intent
filters over the non-excluded topics, then divide by that candidate's total
(rows are normalised). Columns are ordered by the summed proportion across
candidates. The page is SSR'd in the default state (全部 / 生活 excluded /
both intents) so it is complete without JS; the client recomputes from
/api/topic-index.json only once the user changes a filter.
"""

from __future__ import annotations

import json
import math
import shutil
from typing import Any, Dict, Iterable, List, Optional, Set

from . import shell as S

OUT_DIR = S.SITE_ROOT / "spectrum"
DATA_DIR = S.SITE_ROOT / "data" / "topic"
FALLBACK_TOPIC = "生活"
TOPICS = list(S.TOPIC_SLUGS)            # canonical chip order
INTENTS = list(S.INTENT_LABELS)         # self_initiated, responsive
SEQ_BINS = [0.03, 0.06, 0.10, 0.15, 0.22]  # ratio → --seq-1..6 (keep in sync with spectrum.js)
SEQ_LEGEND = ["0", "<3%", "3–6%", "6–10%", "10–15%", "15–22%", "≥22%"]
RANGES = [("全部", 0), ("近 30 天", 30), ("近 14 天", 14), ("近 7 天", 7)]
SSR_POSTS = 30
PAGE_SIZE = 60
KEEP_POST_KEYS = ("id", "candidateId", "platform", "url", "postedAt", "text", "imageUrl",
                  "imageAspect", "topics", "postingIntent")
FOOTNOTE = ("顏色深淺＝該議題佔該候選人議題發文的比例（每列各自正規化）；粗框＝該候選人聲量最高的議題；"
            "「·」＝無相關貼文。點表頭議題名稱可看該議題的跨候選人比較。")


# ---------------------------------------------------------------------------
# Maths (mirrors spectrum.js)
# ---------------------------------------------------------------------------

def compute(index_posts: Iterable[Dict[str, Any]], excluded: Set[str],
            excluded_intents: Set[str] = frozenset()) -> Dict[str, Dict[str, Any]]:
    per: Dict[str, Dict[str, Any]] = {}
    for post in index_posts:
        if (post.get("postingIntent") or "self_initiated") in excluded_intents:
            continue
        bucket = per.setdefault(post["candidateId"], {"totals": {}, "count": 0})
        counted = False
        for topic, score in (post.get("topicScores") or {}).items():
            if topic in excluded:
                continue
            bucket["totals"][topic] = bucket["totals"].get(topic, 0.0) + float(score or 0)
            counted = True
        if counted:
            bucket["count"] += 1
    out: Dict[str, Dict[str, Any]] = {}
    for cid, bucket in per.items():
        grand = sum(bucket["totals"].values())
        props = {t: v / grand for t, v in bucket["totals"].items()} if grand > 0 else {}
        out[cid] = {"props": props, "count": bucket["count"]}
    return out


def column_order(result: Dict[str, Dict[str, Any]]) -> List[str]:
    totals: Dict[str, float] = {}
    for entry in result.values():
        for topic, value in entry["props"].items():
            totals[topic] = totals.get(topic, 0.0) + value
    return sorted((t for t in totals if totals[t] > 0), key=lambda t: (-totals[t], TOPICS.index(t) if t in TOPICS else 99))


def seq_step(value: float) -> int:
    if value <= 0:
        return 0
    return 1 + sum(1 for b in SEQ_BINS if value >= b)


def pct(value: float) -> str:
    if value <= 0:
        return "0%"
    if value < 0.005:
        return "<1%"
    return f"{int(math.floor(value * 100 + 0.5))}%"


# ---------------------------------------------------------------------------
# /spectrum/
# ---------------------------------------------------------------------------

def _identity(c: Dict[str, Any], count: int, tag: str = "div") -> str:
    party = c.get("party") or "無黨籍"
    return (f'<a class="spectrum-identity" href="/{S.esc(c["city"])}/{S.esc(c["id"])}/">'
            f'{S.render_avatar(c, "sm")}<span class="spectrum-who-text"><strong>{S.esc(c["name"])}</strong>'
            f'<span class="spectrum-who-meta">{S.esc(party)} · {count:,} 則</span></span></a>')


def _table(data, result: Dict[str, Dict[str, Any]], topics: List[str], order: Dict[str, List[str]]) -> str:
    head = "".join(
        f'<th scope="col" class="spectrum-topic"><a href="/spectrum/{S.topic_slug(t)}/" '
        f'title="看「{S.esc(t)}」議題的跨候選人比較">{S.esc(t)}</a></th>' for t in topics
    )
    rows = []
    for city in data.cities:
        ids = order.get(city["id"]) or []
        if not ids:
            continue
        rows.append(f'<tr class="spectrum-city-row"><th colspan="{len(topics) + 1}" scope="rowgroup">'
                    f'<span class="spectrum-city-label chip-city" data-city="{S.esc(city["id"])}">'
                    f'{S.esc(S.city_label(city["id"], False))}</span></th></tr>')
        for cid in ids:
            c = data.by_id[cid]
            entry = result.get(cid) or {"props": {}, "count": 0}
            props = entry["props"]
            row_max = max(props.values()) if props else 0
            cells = []
            for t in topics:
                v = props.get(t, 0.0)
                if not props:
                    cells.append('<td class="spectrum-cell" data-step="0"><span aria-label="無資料">—</span></td>')
                    continue
                step = seq_step(v)
                cls = "spectrum-cell spectrum-cell-max" if v > 0 and v == row_max else "spectrum-cell"
                label = pct(v) if v > 0 else "·"
                title = f'{c["name"]}｜{t} {pct(v)}' + ("（最高）" if "max" in cls else "")
                cells.append(f'<td class="{cls}" data-step="{step}" title="{S.esc(title)}">{label}</td>')
            rows.append(f'<tr data-candidate="{S.esc(cid)}"><th scope="row" class="spectrum-who">'
                        f'{_identity(c, entry["count"])}</th>{"".join(cells)}</tr>')
    return ('<div class="spectrum-scroll" tabindex="0" role="region" aria-label="議題光譜熱圖（可橫向捲動）">'
            '<table class="spectrum-table"><caption class="sr-only">各候選人議題發文比例</caption>'
            f'<thead><tr><th scope="col" class="spectrum-who-head">候選人</th>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def _cards(data, result: Dict[str, Dict[str, Any]], order: Dict[str, List[str]]) -> str:
    out = []
    for city in data.cities:
        ids = order.get(city["id"]) or []
        if not ids:
            continue
        cards = []
        for cid in ids:
            c = data.by_id[cid]
            entry = result.get(cid) or {"props": {}, "count": 0}
            top = sorted(entry["props"].items(), key=lambda kv: -kv[1])[:5]
            if top:
                meters = "".join(
                    f'<div class="meter-row{" is-max" if i == 0 else ""}"><a class="meter-label" href="/spectrum/{S.topic_slug(t)}/">{S.esc(t)}</a>'
                    f'<div class="meter" role="img" aria-label="{S.esc(t)} {pct(v)}"><span class="meter-fill" style="--v:{v:.4f}"></span></div>'
                    f'<span class="meter-value">{pct(v)}</span></div>' for i, (t, v) in enumerate(top)
                )
            else:
                meters = '<p class="spectrum-card-empty">目前的篩選條件下沒有議題貼文。</p>'
            cards.append(f'<article class="card spectrum-card" data-candidate="{S.esc(cid)}">'
                         f'{_identity(c, entry["count"])}<div class="spectrum-card-meters">{meters}</div></article>')
        out.append(f'<section class="spectrum-card-city"><h2 class="spectrum-card-city-title chip-city" data-city="{S.esc(city["id"])}">'
                   f'{S.esc(S.city_label(city["id"], False))}</h2>{"".join(cards)}</section>')
    return f'<div class="spectrum-cards">{"".join(out)}</div>'


def _legend() -> str:
    sw = "".join(f'<span class="spectrum-legend-step" data-step="{i}">{S.esc(lbl)}</span>' for i, lbl in enumerate(SEQ_LEGEND))
    return ('<div class="spectrum-legend" aria-label="圖例">'
            f'<span class="spectrum-legend-title">議題比例</span><span class="spectrum-legend-scale">{sw}</span>'
            '<span class="spectrum-legend-max"><span class="spectrum-legend-maxbox" aria-hidden="true"></span>該候選人最高議題</span></div>')


def _sorted_ids(data, city_ids: List[str], sort_id: str) -> List[str]:
    if sort_id == "count":
        return sorted(city_ids, key=lambda i: -(data.by_id[i].get("postCount") or 0))
    return sorted(city_ids, key=lambda i: -S.epoch(data.by_id[i].get("latestPostAt")))


def render_index(data) -> None:
    index = data.topic_index
    excluded = {FALLBACK_TOPIC}
    result = compute(index, excluded)
    topics = column_order(result)
    sort_id = "latest"   # the client re-picks at random (neutral ordering) on load
    order = {city["id"]: _sorted_ids(data, city["candidateIds"], sort_id) for city in data.cities}
    intent_counts = {k: 0 for k in INTENTS}
    for p in index:
        k = p.get("postingIntent") or "self_initiated"
        intent_counts[k] = intent_counts.get(k, 0) + 1

    range_seg = "".join(f'<button type="button" data-range="{d}" aria-pressed="{"true" if d == 0 else "false"}">{lbl}</button>'
                        for lbl, d in RANGES)
    topic_chips = "".join(
        S.render_chip(t, pressed=t not in excluded, cls="spectrum-toggle",
                      attrs={"data-topic": t, "title": "已排除，點擊恢復" if t in excluded else "點擊排除"})
        for t in TOPICS
    )
    intent_chips = "".join(
        S.render_chip(S.INTENT_LABELS[k], pressed=True, count=f"{intent_counts.get(k, 0):,}", cls="spectrum-toggle",
                      attrs={"data-intent": k, "title": "點擊排除"})
        for k in INTENTS
    )
    sort_seg = "".join(f'<button type="button" data-sort="{sid}" aria-pressed="{"true" if sid == sort_id else "false"}">{lbl}</button>'
                       for sid, lbl in (("latest", "最新更新"), ("count", "貼文數")))
    controls = (
        '<section class="spectrum-controls card" aria-label="篩選">'
        f'<div class="filter-row"><span class="filter-label">時間範圍</span><div class="seg" role="group" aria-label="時間範圍" data-control="range">{range_seg}</div></div>'
        f'<div class="filter-row"><span class="filter-label">議題</span><div class="chips" data-control="topics">{topic_chips}</div></div>'
        f'<div class="filter-row"><span class="filter-label">發文動機</span><div class="chips" data-control="intents">{intent_chips}</div></div>'
        f'<div class="filter-row"><span class="filter-label">排序</span><div class="seg" role="group" aria-label="候選人排序" data-control="sort" '
        f'title="預設排序於每次載入時在兩個中性指標間隨機選擇，避免固定順序暗示立場">{sort_seg}</div></div>'
        '<p class="spectrum-status" role="status" aria-live="polite" hidden></p>'
        '</section>'
    )
    boot = {
        "topics": TOPICS,
        "fallback": FALLBACK_TOPIC,
        "bins": SEQ_BINS,
        "cities": [{"id": c["id"], "candidateIds": c["candidateIds"]} for c in data.cities],
        "candidates": {c["id"]: {k: c.get(k) for k in ("id", "name", "city", "party", "avatarUrl", "postCount", "latestPostAt")}
                       for c in data.candidates},
        "initial": {cid: {"props": {t: round(v, 6) for t, v in e["props"].items()}, "count": e["count"]}
                    for cid, e in result.items()},
        "intentCounts": intent_counts,
    }
    boot_json = json.dumps(boot, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    lede = ("比較六都候選人把公開發文的聲量放在哪些議題上。每一列是一位候選人：格子裡的百分比是該議題佔他／她議題發文的比例"
            "（同一篇貼文可同時屬於數個議題，依 AI 分類分數加權），顏色越深比例越高。"
            "日常生活類貼文（「生活」）預設不列入計算，可在下方議題篩選中加回。")
    body = (
        S.page_head("議題光譜", S.esc(lede), eyebrow="Topic spectrum")
        + controls
        + '<section class="spectrum-result" aria-label="議題光譜">'
        + '<div class="spectrum-view">' + _table(data, result, topics, order) + _cards(data, result, order) + "</div>"
        + _legend()
        + f'<p class="spectrum-footnote">{S.esc(FOOTNOTE)}</p>'
        + "</section>"
        + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(data.generated_at.isoformat(), True))}（GMT+8）・'
          '議題與發文動機由 AI 分類，僅供參考；本站為非官方觀測站。</p>'
        + f'<script type="application/json" id="spectrum-boot">{boot_json}</script>'
    )
    html = S.layout("spectrum", "議題光譜",
                    "六都市長候選人公開發文的議題比例光譜：同城市候選人並排比較，看每個人把聲量放在哪些議題上。",
                    "/spectrum/", body, extra_css=["pages/spectrum.css"], extra_js=["pages/spectrum.js"],
                    body_class="page-spectrum-index")
    S.write_page("/spectrum/", html)


# ---------------------------------------------------------------------------
# /spectrum/<slug>/
# ---------------------------------------------------------------------------

def _topic_stats(data) -> Dict[str, Dict[str, Dict[str, float]]]:
    """cid → {"all": total score, "noLife": total excl. 生活, topic: {self, resp}}."""
    stats: Dict[str, Dict[str, Any]] = {}
    for p in data.topic_index:
        st = stats.setdefault(p["candidateId"], {"all": 0.0, "noLife": 0.0, "topics": {}})
        intent = "responsive" if p.get("postingIntent") == "responsive" else "self_initiated"
        for topic, score in (p.get("topicScores") or {}).items():
            s = float(score or 0)
            st["all"] += s
            if topic != FALLBACK_TOPIC:
                st["noLife"] += s
            bucket = st["topics"].setdefault(topic, {"self_initiated": 0.0, "responsive": 0.0})
            bucket[intent] += s
    return stats


def _slim(post: Dict[str, Any]) -> Dict[str, Any]:
    return {k: post.get(k) for k in KEEP_POST_KEYS if k in post}


def _topic_nav(current: str) -> str:
    cur = ' aria-current="page"'
    chips = "".join(
        f'<a class="chip" href="/spectrum/{slug}/"{cur if t == current else ""}>{S.esc(t)}</a>'
        for t, slug in S.TOPIC_SLUGS.items()
    )
    return (f'<nav class="topic-nav" aria-label="其他議題"><a class="chip topic-nav-back" href="/spectrum/">'
            f'{S.icon("spectrum")}<span>光譜總覽</span></a>{chips}</nav>')


def render_topic(data, topic: str, stats: Dict[str, Dict[str, Any]], posts_all: List[Dict[str, Any]]) -> None:
    slug = S.topic_slug(topic)
    posts = [p for p in posts_all if topic in (p.get("topics") or [])]
    counts: Dict[str, int] = {}
    for p in posts:
        counts[p["candidateId"]] = counts.get(p["candidateId"], 0) + 1
    is_life = topic == FALLBACK_TOPIC

    # -- data pages for the river continuation
    out_dir = DATA_DIR / slug
    pages = max(1, math.ceil(len(posts) / PAGE_SIZE)) if posts else 0
    for n in range(pages):
        chunk = posts[n * PAGE_SIZE:(n + 1) * PAGE_SIZE]
        S.write_text(out_dir / f"page-{n + 1}.json", json.dumps(
            {"version": 1, "topic": topic, "slug": slug, "page": n + 1, "pages": pages, "pageSize": PAGE_SIZE,
             "total": len(posts), "posts": [_slim(p) for p in chunk]},
            ensure_ascii=False, separators=(",", ":")))

    # -- ranking
    rows = []
    for c in data.candidates:
        st = stats.get(c["id"]) or {"all": 0.0, "noLife": 0.0, "topics": {}}
        denom = st["all"] if is_life else st["noLife"]
        b = st["topics"].get(topic) or {"self_initiated": 0.0, "responsive": 0.0}
        share = (b["self_initiated"] + b["responsive"]) / denom if denom > 0 else 0.0
        self_share = b["self_initiated"] / denom if denom > 0 else 0.0
        rows.append((c, share, self_share, share - self_share))
    rows.sort(key=lambda r: (-r[1], -counts.get(r[0]["id"], 0)))
    scale = max((r[1] for r in rows), default=0) or 1.0
    kw_by_c = (data.topic_details.get("topics") or {}).get(topic) or {}
    rank_html = []
    for c, share, s_self, s_resp in rows:
        n = counts.get(c["id"], 0)
        kws = kw_by_c.get(c["id"]) or []
        kw_html = "".join(f'<span class="chip-soft topic-kw">{S.esc(k)}<span class="chip-count">{int(v)}</span></span>'
                          for k, v in kws[:8])
        resp_pct = pct(s_resp / share) if share > 0 else "0%"
        aria = f"{c['name']} {pct(share)}，主動 {pct(s_self)}、回應 {pct(s_resp)}"
        rank_html.append(
            f'<li class="topic-rank" data-candidate="{S.esc(c["id"])}">'
            f'<div class="meter-row topic-rank-row">'
            f'<a class="topic-rank-who" href="/{S.esc(c["city"])}/{S.esc(c["id"])}/">{S.render_avatar(c, "xs")}'
            f'<span class="topic-rank-name">{S.esc(c["name"])}</span>'
            f'<span class="topic-rank-city chip-city" data-city="{S.esc(c["city"])}">{S.esc(S.city_label(c["city"]))}</span></a>'
            f'<div class="meter meter-lg" role="img" aria-label="{S.esc(aria)}" title="{S.esc(aria)}">'
            f'<span class="meter-fill" style="--v:{s_self / scale:.4f}"></span>'
            f'<span class="meter-fill" style="--v:{s_resp / scale:.4f}"></span></div>'
            f'<span class="meter-value"><strong>{pct(share)}</strong><span class="topic-rank-n">{n:,} 則'
            f'{"・回應 " + resp_pct if s_resp > 0 else ""}</span></span></div>'
            + (f'<div class="topic-rank-kws">{kw_html}</div>' if kw_html else "")
            + "</li>"
        )
    denom_note = "該候選人全部議題分數" if is_life else "該候選人「生活」以外的議題分數"
    ranking = (
        '<section class="section topic-ranking"><div class="section-head"><h2>跨候選人比較</h2></div>'
        f'<p class="topic-note">比例＝本議題的 AI 分類分數佔{denom_note}的比例（與光譜預設設定一致）；'
        '條長以本頁最高者為滿格，深色為主動發文、淺色為回應他方觀點。每列下方為該候選人本議題最常出現的關鍵字。</p>'
        '<div class="legend topic-legend"><span><span class="legend-swatch" style="background:var(--seq-5)"></span>主動發文</span>'
        '<span><span class="legend-swatch" style="background:var(--seq-3)"></span>回應他方觀點</span></div>'
        f'<ol class="topic-rank-list">{"".join(rank_html)}</ol></section>'
    )

    # -- keywords overall
    kw_total: Dict[str, int] = {}
    for per in kw_by_c.values():
        for k, v in per:
            kw_total[k] = kw_total.get(k, 0) + int(v)
    top_kw = sorted(kw_total.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    keywords = ""
    if top_kw:
        keywords = ('<section class="section topic-keywords"><div class="section-head"><h2>關鍵字</h2>'
                    '<span class="small muted">全部候選人合計出現次數，前 20</span></div><div class="row">'
                    + "".join(S.render_chip(k, count=v) for k, v in top_kw) + "</div></section>")

    # -- river
    n_cands = sum(1 for c in data.candidates if counts.get(c["id"]))
    if posts:
        picker_chips = [S.render_chip("全部", pressed=True, count=f"{len(posts):,}", cls="topic-pick", attrs={"data-candidate": "", "data-count": len(posts)})]
        for c in data.candidates:
            n = counts.get(c["id"], 0)
            if n:
                picker_chips.append(S.render_chip(c["name"], pressed=False, count=n, cls="topic-pick", party=c.get("party"),
                                                  attrs={"data-candidate": c["id"], "data-count": n}))
        ctx = data.post_ctx()
        ssr = "".join(S.render_post(p, ctx) for p in posts[:SSR_POSTS])
        more_hidden = "" if len(posts) > SSR_POSTS else " hidden"
        river = (
            '<section class="section topic-river" aria-labelledby="topic-river-title">'
            '<div class="section-head"><h2 id="topic-river-title">相關貼文</h2>'
            f'<span class="small muted topic-river-count">共 {len(posts):,} 則・新到舊</span></div>'
            f'<div class="filter-row topic-picker"><span class="filter-label">候選人</span><div class="chips">{"".join(picker_chips)}</div></div>'
            f'<div class="feed topic-feed" id="topic-feed" data-slug="{slug}" data-total="{len(posts)}" data-pages="{pages}" '
            f'data-page-size="{PAGE_SIZE}" data-ssr="{min(SSR_POSTS, len(posts))}">{ssr}</div>'
            f'<div class="feed-more"{more_hidden}><button class="btn" type="button" id="topic-more">載入更多</button></div>'
            '<p class="topic-river-status small muted" role="status" aria-live="polite" hidden></p>'
            "</section>"
        )
        lede = (f"{n_cands} 位候選人共 {len(posts):,} 則貼文被 AI 歸類為「{S.esc(topic)}」議題。"
                "下方先比較各候選人投入這個議題的比例，再依時間列出所有相關貼文；可複選候選人縮小範圍。")
    else:
        river = ('<section class="section topic-river">'
                 + S.render_empty("目前沒有這個議題的貼文", "等候選人發布相關貼文並完成分類後，會出現在這裡。",
                                  '<a class="btn btn-sm" href="/spectrum/">回到議題光譜</a>')
                 + "</section>")
        lede = f"目前尚無被歸類為「{S.esc(topic)}」議題的貼文。"
    if is_life:
        lede += "「生活」是無法歸入其他議題時的預設分類（節慶問候、日常紀錄等），在議題光譜中預設不列入計算。"

    body = (
        S.page_head(topic, lede, eyebrow="議題光譜")
        + _topic_nav(topic)
        + ranking + keywords + river
        + f'<p class="snapshot">資料快照：{S.esc(S.fmt_time_tpe(data.generated_at.isoformat(), True))}（GMT+8）・'
          '議題與發文動機由 AI 分類，僅供參考；所有貼文皆連回原文。</p>'
    )
    html = S.layout("topic", f"{topic}議題比較",
                    f"六都市長候選人在「{topic}」議題的公開發文比較：各候選人投入比例、關鍵字與所有相關貼文。",
                    f"/spectrum/{slug}/", body, extra_css=["pages/spectrum.css"], extra_js=["pages/spectrum.js"],
                    body_class="page-spectrum-topic")
    S.write_page(f"/spectrum/{slug}/", html)


def render(data) -> None:
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    render_index(data)
    stats = _topic_stats(data)
    posts_all = data.all_posts()
    for topic in S.TOPIC_SLUGS:
        render_topic(data, topic, stats, posts_all)
