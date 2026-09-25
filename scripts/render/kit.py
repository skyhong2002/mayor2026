"""Dev-only design kit at /_kit/ — renders the shell and every shared
component with real data so page engineers can see (and screenshot) them."""

from __future__ import annotations

import datetime as dt
import shutil

from . import shell as S

OUT = S.SITE_ROOT / "_kit"


def _story_strip(data) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    items = []
    ordered = sorted(data.candidates, key=lambda c: S.epoch(c.get("latestPostAt")), reverse=True)
    for c in ordered:
        recent = sum(1 for p in data.posts_for(c["id"])
                     if (now - (S.parse_ts(p.get("postedAt")) or now - dt.timedelta(days=99))).total_seconds() < 172800)
        badge = f'<span class="story-badge">{recent}</span>' if recent else ""
        src = S.asset_abs(c.get("avatarUrl"))
        img = f'<img src="{S.esc(src)}" alt="" width="58" height="58" loading="lazy">' if src else \
            f'<span class="avatar-initial">{S.esc(c["name"][:1])}</span>'
        items.append(
            f'<a class="story-item" href="/?candidate={S.esc(c["id"])}" data-party="{S.party_slug(c.get("party"))}">'
            f'<span class="story-ring">{img}{badge}</span><span class="story-name">{S.esc(c["name"])}</span></a>'
        )
    return f'<nav class="story-strip" aria-label="候選人">{"".join(items)}</nav>'


def _deck(data) -> str:
    ctx = data.post_ctx(show_city=False)
    cols = []
    for city in ("taipei", "taichung", "kaohsiung"):
        posts = [p for p in data.all_posts() if data.by_id[p["candidateId"]]["city"] == city][:8]
        body = "".join(S.render_post(p, ctx) for p in posts)
        cols.append(
            f'<section class="feed-col" data-city="{city}" aria-label="{S.city_label(city, False)}">'
            f'<header class="feed-col-head"><span class="feed-col-dot"></span>'
            f'<h2 class="feed-col-title">{S.city_label(city, False)}</h2>'
            f'<div class="feed-col-tools"><button class="col-btn" type="button" aria-expanded="false">{S.icon("filter")}<span>篩選</span></button>'
            f'<button class="col-btn" type="button" aria-label="移除欄位">{S.icon("close")}</button></div></header>'
            f'<div class="col-body">{body}<div class="feed-more"><button class="btn btn-sm" type="button">載入更多</button></div></div></section>'
        )
    cols.append(f'<button class="feed-col-add" type="button">{S.icon("plus")}<span>加欄</span></button>')
    return f'<div class="feed-cols" style="--deck-h: 760px">{"".join(cols)}</div>'


def _single_feed(data) -> str:
    posts = data.all_posts()
    picks = [p for p in posts if p.get("imageUrl")][:2] + [p for p in posts if len(p.get("text") or "") > 600][:1]
    picks += [p for p in posts if (p.get("postingIntent") or {}).get("type") == "responsive"][:1]
    return f'<div class="feed">{"".join(S.render_post(p, data) for p in picks)}</div>'


def _components(data) -> str:
    c0 = data.candidates[0]
    tiles = "".join(
        f'<div class="stat-tile"><span class="stat-value">{v}</span><span class="stat-label">{l}</span><span class="stat-hint">{h}</span></div>'
        for v, l, h in [
            (f"{len(data.candidates)}", "監看候選人", "六都"),
            (f"{len(data.all_posts()):,}", "已收錄貼文", "僅 AI 已分類"),
            (f"{sum(len(s.get('accounts') or []) for s in data.sources)}", "監看帳號", "含官網、Podcast"),
            (S.fmt_time_tpe(data.generated_at.isoformat()), "資料快照", "GMT+8"),
        ]
    )
    chips = "".join([
        S.render_chip("全部", pressed=True, count=len(data.all_posts())),
        S.render_chip("Facebook", pressed=False, icon_name="facebook"),
        S.render_chip("Threads", pressed=False, icon_name="threads"),
        S.render_chip("交通", href="/spectrum/transport/"),
        S.render_chip("民進黨", party="民進黨"), S.render_chip("國民黨", party="國民黨"),
        S.render_chip("司法改革黨", party="司法改革黨"), S.render_chip("無黨籍", party=""),
        *[S.render_chip(S.city_label(c), city=c) for c in S.CITY_ORDER],
        S.render_chip("議會監督", soft=True),
    ])
    badges = "".join(S.render_badge(s, l) for s, l in
                     [("ok", "正常"), ("warn", "部分異常"), ("error", "抓取失敗"), ("paused", "節流中"), ("pending", "等待排程")])
    buttons = (f'<button class="btn btn-primary" type="button">{S.icon("rss")}訂閱 RSS</button>'
               f'<a class="btn" href="/api/candidates.json">{S.icon("json")}JSON</a>'
               '<button class="btn btn-ghost" type="button">取消</button>'
               '<button class="btn btn-sm" type="button">小按鈕</button>'
               f'<button class="btn btn-sm btn-icon" type="button" aria-label="分享">{S.icon("share")}</button>'
               '<button class="btn" type="button" disabled>停用</button>')
    seg = ('<div class="seg" role="group" aria-label="城市"><button type="button" aria-pressed="true">全部</button>'
           + "".join(f'<button type="button" aria-pressed="false">{S.city_label(c)}</button>' for c in S.CITY_ORDER) + "</div>")
    spec = max(data.spectrum or [{}], key=lambda r: r.get("postCount", 0))
    props = sorted((spec.get("topicProportions") or {}).items(), key=lambda kv: -kv[1])[:6]
    meters = "".join(
        f'<div class="meter-row"><a class="meter-label" href="/spectrum/{S.topic_slug(t)}/">{S.esc(t)}</a>'
        f'<div class="meter" role="img" aria-label="{S.esc(t)} {v:.0%}"><span class="meter-fill" style="--v:{v:.4f}"></span></div>'
        f'<span class="meter-value">{v:.0%}</span></div>' for t, v in props
    )
    stacked = ('<div class="meter-row"><span class="meter-label">主動／回應</span><div class="meter meter-lg">'
               '<span class="meter-fill" style="--v:0.62"></span><span class="meter-fill" style="--v:0.21"></span></div>'
               '<span class="meter-value">83%</span></div>')
    rows = "".join(
        f'<tr><td><div class="table-identity">{S.render_avatar(c, "sm")}<a href="/{c["city"]}/{c["id"]}/">{S.esc(c["name"])}</a></div></td>'
        f'<td>{S.render_chip(S.city_label(c["city"]), city=c["city"], soft=True)}</td>'
        f'<td>{S.render_chip(c.get("party") or "無黨籍", party=c.get("party"), soft=True)}</td>'
        f'<td class="num">{c.get("postCount", 0):,}</td><td class="num muted">{S.fmt_time_tpe(c.get("latestPostAt"))}</td>'
        f'<td>{S.render_badge("ok", "正常")}</td></tr>'
        for c in data.candidates[:6]
    )
    table = ('<div class="table-wrap"><table class="table"><thead><tr><th data-sort="name" aria-sort="ascending">候選人</th>'
             '<th>城市</th><th>政黨</th><th class="num" data-sort="posts">已收錄</th><th class="num">最新內容</th><th>狀態</th></tr></thead>'
             f"<tbody>{rows}</tbody></table></div>")
    avatars = "".join(S.render_avatar(c, size) for c, size in zip(data.candidates[:4], ("xs", "sm", "md", "lg")))
    notices = ('<div class="notice">' + S.icon("about") + '<p>議題與發文動機由 AI 分類，僅供參考；點擊 chip 可查看分類理由。</p></div>'
               '<div class="notice" data-tone="warn">' + S.icon("status") + '<p>Facebook 抓取依預算配速，最新貼文可能延遲數小時。</p></div>'
               '<div class="notice" data-tone="danger"><p>目前有 2 個來源抓取失敗。</p></div>'
               '<div class="notice" data-tone="success"><p>所有來源運作正常。</p></div>')
    empties = S.render_empty("目前的篩選條件下沒有貼文", "試著移除部分議題或平台篩選。",
                             '<button class="btn btn-sm" type="button">清除篩選</button>')
    card = (f'<a class="card" href="/{c0["city"]}/{c0["id"]}/"><div class="row">{S.render_avatar(c0, "md")}'
            f'<div><p class="card-title">{S.esc(c0["name"])}</p><p class="card-meta">{S.city_label(c0["city"], False)}・{S.esc(c0["party"])}</p></div></div></a>')
    filter_row = ('<div class="filter-row"><span class="filter-label">平台</span><div class="chips">'
                  + "".join(S.render_chip(S.PLATFORM_LABELS[p], pressed=(p == "facebook"), icon_name=p)
                            for p in ("facebook", "instagram", "threads", "youtube", "x", "website", "podcast"))
                  + "</div></div>")
    icons = "".join(f'<span class="chip-soft" title="{n}">{S.icon(n)}<span>{n}</span></span>' for n in S.ICON_NAMES)

    def sec(title, inner):
        return f'<section class="section"><div class="section-head"><h2>{title}</h2></div>{inner}</section>'

    return "".join([
        sec("Stat tiles（.grid-4 .stat-tile）", f'<div class="grid-4">{tiles}</div>'),
        sec("Chips", f'<div class="row">{chips}</div>'),
        sec("Filter row ＋ seg", f'<div class="stack">{filter_row}{seg}</div>'),
        sec("Buttons", f'<div class="row">{buttons}</div>'),
        sec("Status badges", f'<div class="row">{badges}</div>'),
        sec("Avatars（外環 = 政黨色）", f'<div class="row" style="gap:20px">{avatars}</div>'),
        sec(f"Meter（{S.esc(data.by_id[spec['candidateId']]['name'])} 議題比例）", f'<div class="card"><div class="stack" style="--stack-gap:4px">{meters}{stacked}</div></div>'),
        sec("Table（harmonica Directory）", table),
        sec("Cards", f'<div class="grid-3">{card}{card}{card}</div>'),
        sec("Notices", f'<div class="stack">{notices}</div>'),
        sec("Empty state", empties),
        sec("Icons", f'<div class="row">{icons}</div>'),
    ])


def render(data) -> None:
    shutil.rmtree(OUT, ignore_errors=True)
    body = (
        S.page_head("元件總覽", "開發用頁面：app 殼、共用元件與真實資料的貼文卡。不公開、不列入 sitemap。",
                    f'<a class="btn btn-sm" href="/">{S.icon("home")}首頁</a>', eyebrow="Design kit")
        + _story_strip(data)
        + '<section class="section"><div class="section-head"><h2>多欄河道（.feed-cols）</h2></div>' + _deck(data) + "</section>"
        + '<section class="section reading"><div class="section-head"><h2>單欄河道（.feed）</h2></div>'
        + _single_feed(data) + "</section>" + _components(data)
        + f'<p class="snapshot">資料快照：{S.fmt_time_tpe(data.generated_at.isoformat(), True)}（GMT+8）・本站為非官方觀測站。</p>'
    )
    html = S.layout("kit", "元件總覽", "開發用元件總覽。", "/_kit/", body, noindex=True, body_class="layout-wide")
    S.write_page("/_kit/", html)
