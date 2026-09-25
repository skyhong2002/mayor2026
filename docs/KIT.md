# KIT — shared renderer and component API (phase 1)

Read with `docs/DESIGN.md`. Source: `scripts/render/shell.py`, `scripts/render/data.py`, `site/assets/{tokens.css,styles.css,shell.js}`.
Live reference: `python3 scripts/generate_site_pages.py --kit` → http://127.0.0.1:8743/_kit/ (dev only; removed when `--kit` is absent).
Python must run on **3.9**: start every file with `from __future__ import annotations`.

## Adding a page module
```python
# scripts/render/home.py
from __future__ import annotations
import shutil
from . import shell as S

def render(data) -> None:            # called by generate_site_pages.py
    shutil.rmtree(S.SITE_ROOT / "…your dir…", ignore_errors=True)   # own + clean your outputs
    body = S.page_head("標題", "導言") + "…"
    html = S.layout("home", "最新", "描述", "/", body, extra_css=["pages/home.css"], extra_js=["pages/home.js"],
                    jsonld={...}, body_class="layout-deck")
    S.write_page("/", html)           # → site/index.html ; "/spectrum/x/" → site/spectrum/x/index.html
```
Module order: home, candidate, directory, spectrum, policy, status, search. Put page assets in `site/assets/pages/` (auto-included in the `?v=` hash).
`/spectrum/topic/<slug>/` redirect stubs are written by the orchestrator after all modules.

## render/shell.py
| API | Notes |
|---|---|
| `esc(v)` | escapes `& < > " '` (same table as `MO.esc`) |
| `asset_url("styles.css" \| "pages/x.js")` | `/assets/…?v=<10-hex>`; `asset_hash()` (= `generate_site_pages.asset_version()`) |
| `asset_abs("assets/a.webp")` | → `/assets/a.webp` (http/abs pass through, None → None) |
| `head(title, description, path, og_image=None, jsonld=None, extra_css=(), noindex=False)` | inner `<head>`; title gets `｜2026 市長官方來源觀測站` |
| `layout(page_id, title, description, path, body_html, extra_css=(), extra_js=(), jsonld=None, og_image=None, noindex=False, body_class="")` | full document; body goes in `<main class="page" id="main">`. page_id highlights nav: home, spectrum/topic, policy, source/directory/candidate/source-detail, search, feeds, status, about |
| `page_head(title, lede_html="", actions_html="", eyebrow="")` | `.page-head` block (lede is raw HTML — escape yourself) |
| `render_post(post, ctx)` | canonical card, see below. `ctx` = `data` or `data.post_ctx(show_city=False, show_json=True)` |
| `render_avatar(entity, size="sm", href=None, cls="", label=None)` | size xs 24 / sm 36 / md 48 / lg 88; ring = party colour |
| `render_chip(label, href=None, *, soft=False, cls="", count=None, pressed=None, party=None, city=None, icon_name=None, attrs=None)` | `<a>` if href, `<button aria-pressed>` if pressed is not None, else `<span>` |
| `render_badge(state, label)` / `render_empty(title, body="", action_html="")` | |
| `icon(name, cls="icon")` | home spectrum match people search rss status about more sun moon system share external json filter plus close chevron facebook instagram threads youtube x website podcast line tiktok (`line_oa`/`line_openchat` → line; unknown → website) |
| `party_slug(party)` | dpp / kmt / tpp / jrp / none |
| `city_label(slug, short=True)` | 臺中 / 臺中市 |
| `topic_slug(topic)`, `TOPIC_SLUGS`, `SLUG_TOPICS`, `PLATFORM_LABELS`, `INTENT_LABELS`, `CITY_ORDER`, `CITY_LABELS`, `CITY_SHORT`, `nav_items` | |
| `parse_ts(iso)` → aware datetime or None; `epoch(iso)` → int (0 if missing) | handles Z / +00:00 / +08:00 / None |
| `fmt_time_tpe(iso, with_year=None)` → `9/25 12:00`; `fmt_date_tpe(iso)` → `2026/9/25`; `rel_time_tpe(iso, now=None)` | Asia/Taipei |
| `read_json(path, default)`, `write_text(path, text)`, `write_page(route, html)`, `write_redirect(route, target, title)` | relative paths are under `site/` |
| constants | `SITE_ROOT`, `SITE_NAME`, `BASE_URL`, `GITHUB_URL`, `REPORT_URL` |

## render/data.py — `data = data_mod.load()` (cached; roster-filtered everywhere)
`.candidates` (list, candidates.json order) · `.by_id` · `.roster` (set) · `.cities` ([{id,label,candidateIds}] fixed order) · `.candidates_in(city)` ·
`.sources` / `.sources_by_id` (with `accounts`) · `.posts_for(cid)` (lazy, newest first) · `.all_posts()` (merged, newest first) · `.latest` ·
`.spectrum` · `.topic_index` · `.topic_details` · `.policy_match` · `.qualitative` · `.status` (None if absent) · `.generated_at` (aware dt) · `.post_ctx(**opts)`.
Neutral ordering: when listing candidates, pick the default sort at random between 最新更新 / 貼文數 (client side) and offer a toggle.

## render_post output (identical to `MO.postHTML`)
```html
<article class="feed-post" data-id="youtube:x" data-candidate="ho-hsin-chun" data-city="taichung" data-platform="youtube" data-intent="responsive" data-topics="議會監督,競選" data-ts="1758772806">
 <a class="feed-avatar avatar avatar-sm" data-party="dpp" href="/taichung/ho-hsin-chun/" aria-label="何欣純" tabindex="-1"><img src="/assets/source-avatars/….webp" alt="" width="36" height="36" loading="lazy" decoding="async"></a>
 <div class="feed-content">
  <header class="feed-head"><a class="feed-name" href="/taichung/ho-hsin-chun/">何欣純</a><span class="feed-sep" aria-hidden="true">›</span><a class="feed-city chip-city" data-city="taichung" href="/?city=taichung">臺中</a><time class="feed-time" datetime="{raw postedAt}" data-rel>9/25 12:00</time><a class="feed-plat" href="{url}" target="_blank" rel="noopener" aria-label="在 YouTube 開啟原文" title="YouTube"><svg …></a></header>
  <div class="feed-text" data-clamp>{escaped, linkified, \n→<br>}</div><button class="feed-text-toggle" type="button" hidden>顯示全文</button>
  <a class="feed-media" href="{url}" target="_blank" rel="noopener" tabindex="-1"><img loading="lazy" decoding="async" src="/assets/feed-images/…" alt="" style="aspect-ratio: 0.5625"></a>   <!-- only with image -->
  <div class="feed-tags"><a class="chip-soft chip-topic" href="/spectrum/oversight/">議會監督</a>…<span class="chip-soft chip-intent" data-intent="responsive" title="{reason}">回應他方觀點 87%</span></div>
  <div class="feed-actions"><a class="feed-action" …>{external}<span>原文</span></a><button class="feed-action btn-share" type="button" data-url data-title>{share}<span>分享</span></button><a class="feed-action" href="/api/posts/{cid}.json">{json}<span>JSON</span></a></div>
 </div></article>
```
Missing postedAt → `<span class="feed-time">時間不明</span>`. `show_city=False` drops sep+city (use inside a city column).

## CSS classes (styles.css)
- **Shell**: `.site-header` `.brand .brand-num .brand-sub` `.site-nav` `.nav-item[aria-current=page]` `.nav-label` `.nav-label-short` (tab bar) `.nav-desktop-only` `.nav-more` `.nav-more-menu` `.topbar-search` (phone, right) `.topbar-action` (phone, fixed top-left slot for a page button) `main.page` `.site-footer` `.skip-link`.
- **Body modifiers** (`layout(body_class=…)`): `layout-wide` (main has no max-width) · `layout-deck` (≥700px: main = 100dvh flex column, a direct-child `.feed-cols` fills the rest).
- **Layout**: `.page-head .page-head-text .page-eyebrow .page-lede .page-actions` · `.container` `.reading` (45rem) · `.grid-2/3/4` (auto-fit, collapse) · `.stack` (`--stack-gap`) · `.row` · `.section` (top margin) `.section-head` `.section-title` `.link-more` · `.prose`.
- **Card / stats**: `.card` (`a.card` hover) `.card-title` `.card-meta` · `.stat-tile .stat-value .stat-label .stat-hint`.
- **Chips**: `.chip` (bordered pill, 32px + 44px hit) · `.chip-soft` (26px, filled) · `[aria-pressed|aria-selected=true]` selected · `.chip-count` · `.chip-party[data-party]` / `.chip-city[data-city]` (6px dot; `.chip-city` alone = inline dot + text) · `.chip-topic` · `.chip-intent[data-intent=responsive]` (accent).
- **Buttons / input**: `.btn` `.btn-primary` `.btn-ghost` `.btn-sm` `.btn-icon` (`:disabled`) · `.input`.
- **Avatar**: `.avatar` + `.avatar-xs/sm/md/lg`, `[data-party]` ring, `.avatar-initial` fallback.
- **Table**: `.table-wrap` (x-scroll) `.table` `th[data-sort][aria-sort]` `.num` `.table-identity`.
- **Status**: `.badge-status[data-state=ok|warn|error|paused|pending]` · `.notice[data-tone=info|warn|danger|success]` · `.empty .empty-title .empty-body`.
- **Filters**: `.filter-row` `.filter-label` `.filter-row .chips` · `.seg` (children `button`/`a` with `aria-pressed|aria-selected|aria-current`).
- **Meter**: `.meter` (`.meter-lg`) › `.meter-fill style="--v:.35"` (several fills stack; 2nd = lighter tone, or `data-tone="soft"`) · `.meter-row .meter-label .meter-value` · `.legend .legend-swatch`.
- **Stories**: `.story-strip` (`.has-selection` dims others) `.story-item[data-party][aria-pressed]` `.story-ring` `.story-badge` `.story-name`.
- **Feed**: `.feed` (single column) · `.feed-post …` (above) · `.feed-more` (centred load-more row).
- **Deck**: `.feed-cols` (`--deck-h`, default `100dvh - 24px`) › `.feed-col[data-city]` (380px) › `.feed-col-head .feed-col-dot .feed-col-title .feed-col-count .feed-col-tools .col-btn[aria-expanded]/.is-active` · `.col-filters` · `.col-body` (own scroll) · `.feed-col-add`. <700px: one column — the `.is-active` column, else the first.
- **Utils**: `.sr-only .num .muted .small .xs .mono .ellipsis .snapshot` · `.toast` (driven by `MO.toast`).
- **Tokens**: `--color-*`, `--space-1..16`, `--radius-xs..pill`, `--shadow-raised/-focus`, `--motion-*`, `--layout-*` (sidebar/rail/topbar/tabbar/col), `--party-dpp/kmt/tpp/jrp/none`, `--city-<slug>` + `--city-<slug>-surface`, `--seq-0..6` (accent sequential; 0 = track), `--brand-gradient`. Any `[data-party]` gets `--party`; any `[data-city]` gets `--city` / `--city-surface`.

## window.MO (shell.js; load order icons.js → shell.js → page js, all `defer`)
`MO.theme.get()` → 'dark'|'light'|'system' · `MO.theme.set(v)` · `MO.theme.resolved()` · event `mo:theme` on document ·
`MO.relTime(iso, now?)` · `MO.fmtTime(iso, withYear?)` · `MO.esc` · `MO.formatText(text)` · `MO.postHTML(post, {byId, showCity, showJson})` (byId defaults to the map from `MO.loadCandidates()`) ·
`MO.avatarHTML(c, size, href, cls)` · `MO.icon(name)` · `MO.bindPostBehaviors(root)` (clamp measurement + rel time; share/toggle clicks are delegated globally) · `MO.applyRel(root)` ·
`MO.toast(msg, ms?)` · `MO.share(url, title)` · `MO.copyText(t)` · `MO.fetchJSON(url)` (cached promise) · `MO.loadCandidates()` → byId · `MO.partySlug` · `MO.assetAbs` · `MO.qs/qsa` · constants `CITY_ORDER CITY_SHORT TOPIC_SLUGS PLATFORM_LABELS INTENT_LABELS`.
Auto on DOMContentLoaded: `[data-rel]` relative time (every 60 s), clamp toggles, nav `aria-current` fallback, `.nav-more` outside-click/Esc close, theme seg. After inserting client-rendered cards call `MO.bindPostBehaviors(container)`.

## Screenshots
Server: `python3 -m http.server 8743 --directory site`. `bash tools/shot.sh <path> <out.png> <width> <height> <dark|light>` (e.g. `/ /tmp/shots/home/d.png 1440 2200 dark`, phone `414 1800`, rail `900 1600`).
`?theme=` previews without persisting. Widths < 500 are rendered in an exact-width iframe (Chrome's minimum window is 500px) and cropped, so phone shots are true 414px layouts. Look at every shot before reporting.
