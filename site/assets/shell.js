/* mayor2026.observe.tw — shared shell behaviour. Exposes window.MO (DESIGN.md §6).
   Icons come from /assets/icons.js (generated from scripts/render/shell.py). */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;
  var TZ = "Asia/Taipei";

  var CITY_SHORT = { taipei: "臺北", "new-taipei": "新北", taoyuan: "桃園", taichung: "臺中", tainan: "臺南", kaohsiung: "高雄" };
  var CITY_ORDER = ["taipei", "new-taipei", "taoyuan", "taichung", "tainan", "kaohsiung"];
  var PARTY_SLUGS = { "民主進步黨": "dpp", "民進黨": "dpp", "中國國民黨": "kmt", "國民黨": "kmt", "台灣民眾黨": "tpp", "臺灣民眾黨": "tpp", "民眾黨": "tpp", "司法改革黨": "jrp" };
  var TOPIC_SLUGS = {
    "交通": "transport", "住宅": "housing", "社福": "welfare", "環境": "environment", "教育": "education",
    "經濟": "economy", "治安": "safety", "醫療": "health", "競選": "campaign", "體育": "sports",
    "文化觀光": "culture", "兩岸外交": "cross-strait", "防災": "disaster", "議會監督": "oversight", "生活": "life"
  };
  var PLATFORM_LABELS = {
    website: "官網", facebook: "Facebook", instagram: "Instagram", threads: "Threads", youtube: "YouTube",
    x: "X", line_oa: "LINE 官方帳號", line_openchat: "LINE 社群", tiktok: "TikTok", podcast: "Podcast"
  };
  var PLATFORM_ICON = { line_oa: "line", line_openchat: "line" };
  var INTENT_LABELS = { self_initiated: "主動發文", responsive: "回應他方觀點" };

  function qs(sel, el) { return (el || doc).querySelector(sel); }
  function qsa(sel, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(sel)); }

  var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(v) { return v == null ? "" : String(v).replace(/[&<>"']/g, function (c) { return ESC[c]; }); }
  /* http(s) URLs and (unless external-only) root-absolute paths; anything else → "". Still needs esc(). */
  function safeUrl(v, externalOnly) {
    var u = v == null ? "" : String(v).trim();
    if (!u || /[\u0000-\u001f\u007f]/.test(u)) return "";
    if (/^https?:\/\//i.test(u)) return u;
    if (!externalOnly && u.charAt(0) === "/" && u.charAt(1) !== "/" && u.charAt(1) !== "\\") return u;
    return "";
  }

  function icon(name) {
    var icons = window.MO_ICONS || {};
    name = PLATFORM_ICON[name] || name;
    return icons[name] || icons.website || "";
  }

  /* ---------- time ---------- */
  function toDate(v) {
    if (!v) return null;
    var d = v instanceof Date ? v : new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }
  var partsFmt = new Intl.DateTimeFormat("en-US", { timeZone: TZ, year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  function tpeParts(d) {
    var o = {};
    partsFmt.formatToParts(d).forEach(function (p) { o[p.type] = p.value; });
    return { y: +o.year, m: +o.month, d: +o.day, hh: o.hour, mm: o.minute };
  }
  function dayIndex(p) { return Date.UTC(p.y, p.m - 1, p.d) / 86400000; }

  function fmtTime(v, withYear) {
    var d = toDate(v);
    if (!d) return "";
    var p = tpeParts(d);
    if (withYear == null) withYear = p.y !== tpeParts(new Date()).y;
    return (withYear ? p.y + "/" : "") + p.m + "/" + p.d + " " + p.hh + ":" + p.mm;
  }

  function relTime(v, now) {
    var d = toDate(v);
    if (!d) return "";
    now = toDate(now) || new Date();
    var s = (now - d) / 1000;
    if (s < 60) return "剛剛";
    if (s < 3600) return Math.floor(s / 60) + " 分鐘前";
    if (s < 86400) return Math.floor(s / 3600) + " 小時前";
    var p = tpeParts(d), n = tpeParts(now);
    var days = dayIndex(n) - dayIndex(p);
    if (days <= 1) return "昨天";
    if (days < 7) return days + " 天前";
    if (p.y !== n.y) return p.y + "/" + p.m + "/" + p.d;
    return p.m + "/" + p.d;
  }

  function applyRel(rootEl) {
    qsa("time[data-rel][datetime]", rootEl).forEach(function (el) {
      var iso = el.getAttribute("datetime");
      var rel = relTime(iso);
      if (!rel) return;
      if (el.textContent !== rel) el.textContent = rel;
      if (!el.title) el.title = fmtTime(iso, true);
    });
  }

  /* ---------- post card (isomorphic with shell.py render_post) ---------- */
  var URL_RE = /https?:\/\/[^\s<>"'「」『』（）【】，。、！？]+/g;
  var URL_TRAIL = ".,;:!?)]}'\"";
  function linkLabel(url) {
    var l = url.replace(/^https?:\/\/(www\.)?/, "");
    return l.length <= 40 ? l : l.slice(0, 38) + "…";
  }
  function formatText(text) {
    var raw = String(text || "").replace(/\r\n/g, "\n").trim().replace(/\n{3,}/g, "\n\n");
    var out = "", pos = 0, m;
    URL_RE.lastIndex = 0;
    while ((m = URL_RE.exec(raw))) {
      var url = m[0];
      while (url && URL_TRAIL.indexOf(url.charAt(url.length - 1)) !== -1) url = url.slice(0, -1);
      if (!url) continue;
      out += esc(raw.slice(pos, m.index));
      out += '<a href="' + esc(url) + '" target="_blank" rel="noopener nofollow ugc">' + esc(linkLabel(url)) + "</a>";
      pos = m.index + url.length;
      URL_RE.lastIndex = pos;
    }
    out += esc(raw.slice(pos));
    return out.replace(/\n/g, "<br>");
  }
  function partySlug(party) { return PARTY_SLUGS[(party || "").trim()] || "none"; }
  function assetAbs(p) {
    if (!p) return null;
    if (/^(https?:|\/|data:)/.test(p)) return p;
    return "/" + p.replace(/^[./]+/, "");
  }
  function isoOf(v) { return v instanceof Date ? v.toISOString() : String(v || "").trim(); }
  function avatarHTML(c, size, href, cls) {
    var name = c.name || c.displayName || c.handle || "";
    var src = assetAbs(c.avatarUrl);
    var px = { xs: 24, sm: 36, md: 48, lg: 88 }[size] || 36;
    var inner = src
      ? '<img src="' + esc(src) + '" alt="" width="' + px + '" height="' + px + '" loading="lazy" decoding="async">'
      : '<span class="avatar-initial" aria-hidden="true">' + esc(name.slice(0, 1)) + "</span>";
    var classes = [cls, "avatar", "avatar-" + size].filter(Boolean).join(" ");
    var party = partySlug(c.party);
    if (href) return '<a class="' + classes + '" data-party="' + party + '" href="' + esc(href) + '" aria-label="' + esc(name) + '" tabindex="-1">' + inner + "</a>";
    return '<span class="' + classes + '" data-party="' + party + '">' + inner + "</span>";
  }

  function postHTML(post, ctx) {
    ctx = ctx || {};
    var byId = ctx.byId || ctx.by_id || MO._byId || {};
    var showCity = ctx.showCity !== false && ctx.show_city !== false;
    var showJson = ctx.showJson !== false && ctx.show_json !== false;
    var cid = post.candidateId || "";
    var cand = byId[cid] || { name: cid, city: "", party: "" };
    var city = cand.city || "";
    var name = cand.name || cid;
    var platform = post.platform || "website";
    var platLabel = PLATFORM_LABELS[platform] || platform;
    var url = safeUrl(post.url, true);
    var topics = (post.topics || []).filter(Boolean);
    var intent = post.postingIntent && typeof post.postingIntent === "object" ? post.postingIntent : null;
    var candHref = city ? "/" + city + "/" + cid + "/" : "/source/";
    var d = toDate(post.postedAt);
    var ts = d ? Math.floor(d.getTime() / 1000) : 0;

    var head = '<a class="feed-name" href="' + esc(candHref) + '">' + esc(name) + "</a>";
    if (showCity && city) head += '<span class="feed-sep" aria-hidden="true">›</span><a class="feed-city chip-city" data-city="' + esc(city) + '" href="/?city=' + esc(city) + '">' + esc(CITY_SHORT[city] || city) + "</a>";
    if (ts) head += '<time class="feed-time" datetime="' + esc(isoOf(post.postedAt)) + '" data-rel>' + esc(fmtTime(post.postedAt)) + "</time>";
    else head += '<span class="feed-time">時間不明</span>';
    head += url
      ? '<a class="feed-plat" href="' + esc(url) + '" target="_blank" rel="noopener" aria-label="在 ' + esc(platLabel) + ' 開啟原文" title="' + esc(platLabel) + '">' + icon(platform) + "</a>"
      : '<span class="feed-plat" title="' + esc(platLabel) + '">' + icon(platform) + "</span>";

    var body = '<div class="feed-text" data-clamp>' + formatText(post.text) + "</div>" +
      '<button class="feed-text-toggle" type="button" hidden>顯示全文</button>';
    var image = assetAbs(post.imageUrl);
    if (image && url) {
      var a = post.imageAspect;
      var ratio = typeof a === "number" && a > 0 ? String(Math.round(a * 10000) / 10000) : "4/3";
      body += '<a class="feed-media" href="' + esc(url) + '" target="_blank" rel="noopener" tabindex="-1"><img loading="lazy" decoding="async" src="' + esc(image) + '" alt="" style="aspect-ratio: ' + ratio + '"></a>';
    }
    var tags = topics.map(function (t) {
      return '<a class="chip-soft chip-topic" href="/spectrum/' + (TOPIC_SLUGS[t] || "life") + '/">' + esc(t) + "</a>";
    }).join("");
    // Posting-intent chips are intentionally not shown on cards (data-intent stays for filters).
    if (tags) body += '<div class="feed-tags">' + tags + "</div>";
    var shareTitle = name + "：" + String(post.text || "").trim().slice(0, 40);
    var actions = url ? '<a class="feed-action" href="' + esc(url) + '" target="_blank" rel="noopener">' + icon("external") + "<span>原文</span></a>" +
      '<button class="feed-action btn-share" type="button" data-url="' + esc(url) + '" data-title="' + esc(shareTitle) + '">' + icon("share") + "<span>分享</span></button>" : "";
    if (showJson && cid) actions += '<a class="feed-action" href="/api/posts/' + esc(cid) + '.json" title="' + esc(name) + ' 的貼文 JSON">' + icon("json") + "<span>JSON</span></a>";
    body += '<div class="feed-actions">' + actions + "</div>";

    var attrs = ' data-id="' + esc(post.id || "") + '" data-candidate="' + esc(cid) + '" data-city="' + esc(city) +
      '" data-platform="' + esc(platform) + '" data-intent="' + esc(intent && intent.type || "") +
      '" data-topics="' + esc(topics.join(",")) + '" data-ts="' + ts + '"';
    return '<article class="feed-post"' + attrs + ">" + avatarHTML(Object.assign({}, cand, { name: name }), "sm", candHref, "feed-avatar") +
      '<div class="feed-content"><header class="feed-head">' + head + "</header>" + body + "</div></article>";
  }

  /* ---------- behaviours ---------- */
  var toastTimer = null;
  function toast(msg, ms) {
    var el = qs(".toast");
    if (!el) { el = doc.createElement("div"); el.className = "toast"; el.setAttribute("role", "status"); el.setAttribute("aria-live", "polite"); doc.body.appendChild(el); }
    el.textContent = msg;
    el.hidden = false;
    requestAnimationFrame(function () { el.classList.add("is-visible"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.remove("is-visible");
      setTimeout(function () { el.hidden = true; }, 250);
    }, ms || 2200);
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var ta = doc.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      doc.body.appendChild(ta); ta.select();
      try { doc.execCommand("copy") ? resolve() : reject(); } catch (e) { reject(e); }
      ta.remove();
    });
  }

  function share(url, title) {
    if (navigator.share) {
      return navigator.share({ url: url, title: title }).catch(function (err) {
        if (err && err.name === "AbortError") return;
        return copyText(url).then(function () { toast("已複製連結"); });
      });
    }
    return copyText(url).then(function () { toast("已複製連結"); }, function () { toast("無法複製，請手動複製網址"); });
  }

  function measureClamp(el) {
    var btn = el.nextElementSibling;
    if (!btn || !btn.classList.contains("feed-text-toggle")) return;
    if (el.classList.contains("is-expanded")) return;
    btn.hidden = !(el.scrollHeight - el.clientHeight > 2);
  }

  function bindPostBehaviors(rootEl) {
    rootEl = rootEl || doc;
    var clamps = qsa(".feed-text[data-clamp]", rootEl);
    if ("ResizeObserver" in window) {
      if (!MO._ro) MO._ro = new ResizeObserver(function (entries) { entries.forEach(function (e) { measureClamp(e.target); }); });
      clamps.forEach(function (el) { if (!el._moObserved) { el._moObserved = true; MO._ro.observe(el); } measureClamp(el); });
    } else {
      clamps.forEach(measureClamp);
    }
    applyRel(rootEl);
  }

  // Delegated handlers (work for SSR and client-rendered cards alike).
  doc.addEventListener("click", function (ev) {
    var t = ev.target;
    var toggle = t.closest && t.closest(".feed-text-toggle");
    if (toggle) {
      var text = toggle.previousElementSibling;
      var open = text.classList.toggle("is-expanded");
      toggle.textContent = open ? "收合" : "顯示全文";
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      return;
    }
    var sh = t.closest && t.closest(".btn-share");
    if (sh) {
      ev.preventDefault();
      share(sh.getAttribute("data-url") || location.href, sh.getAttribute("data-title") || doc.title);
      return;
    }
    var themeBtn = t.closest && t.closest("[data-theme-set]");
    if (themeBtn) { theme.set(themeBtn.getAttribute("data-theme-set")); return; }
    // Close open .nav-more when clicking outside.
    qsa("details.nav-more[open]").forEach(function (d) { if (!d.contains(t)) d.removeAttribute("open"); });
  });
  doc.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") qsa("details.nav-more[open]").forEach(function (d) { d.removeAttribute("open"); var s = qs("summary", d); if (s) s.focus(); });
  });

  /* ---------- theme ---------- */
  var theme = {
    get: function () {
      try { var v = localStorage.getItem("theme"); return v === "dark" || v === "light" ? v : "system"; } catch (e) { return "system"; }
    },
    resolved: function () {
      var a = root.getAttribute("data-theme");
      if (a === "dark" || a === "light") return a;
      return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    },
    set: function (v) {
      try { if (v === "dark" || v === "light") localStorage.setItem("theme", v); else localStorage.removeItem("theme"); } catch (e) {}
      root.removeAttribute("data-theme-preview");
      if (v === "dark" || v === "light") root.setAttribute("data-theme", v); else root.removeAttribute("data-theme");
      syncThemeSeg();
      doc.dispatchEvent(new CustomEvent("mo:theme", { detail: { theme: v, resolved: theme.resolved() } }));
    }
  };
  function syncThemeSeg() {
    var cur = root.hasAttribute("data-theme-preview") ? root.getAttribute("data-theme") : theme.get();
    qsa("[data-theme-set]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-theme-set") === cur ? "true" : "false"); });
  }

  /* ---------- data ---------- */
  var jsonCache = {};
  function fetchJSON(url) {
    if (!jsonCache[url]) {
      jsonCache[url] = fetch(url, { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status + " " + url);
        return r.json();
      }).catch(function (err) { delete jsonCache[url]; throw err; });
    }
    return jsonCache[url];
  }
  function loadCandidates() {
    return fetchJSON("/api/candidates.json").then(function (p) {
      var map = {};
      (p.candidates || []).forEach(function (c) { map[c.id] = c; });
      MO._byId = map;
      return map;
    });
  }

  function markNav() {
    var path = location.pathname;
    var links = qsa(".site-nav a.nav-item[data-nav]");
    if (links.some(function (a) { return a.hasAttribute("aria-current"); })) return;
    var best = null;
    links.forEach(function (a) {
      var h = a.getAttribute("href");
      if (h === "/" ? path === "/" : path.indexOf(h) === 0) { if (!best || h.length > best.getAttribute("href").length) best = a; }
    });
    if (!best && CITY_ORDER.some(function (c) { return path.indexOf("/" + c + "/") === 0; })) best = qs('.site-nav a[data-nav="source"]');
    if (best) best.setAttribute("aria-current", "page");
  }

  var MO = window.MO = {
    theme: theme,
    relTime: relTime,
    fmtTime: fmtTime,
    esc: esc,
    safeUrl: safeUrl,
    postHTML: postHTML,
    avatarHTML: avatarHTML,
    formatText: formatText,
    icon: icon,
    bindPostBehaviors: bindPostBehaviors,
    applyRel: applyRel,
    toast: toast,
    share: share,
    copyText: copyText,
    fetchJSON: fetchJSON,
    loadCandidates: loadCandidates,
    partySlug: partySlug,
    assetAbs: assetAbs,
    qs: qs,
    qsa: qsa,
    CITY_ORDER: CITY_ORDER,
    CITY_SHORT: CITY_SHORT,
    TOPIC_SLUGS: TOPIC_SLUGS,
    PLATFORM_LABELS: PLATFORM_LABELS,
    INTENT_LABELS: INTENT_LABELS
  };

  function init() {
    markNav();
    syncThemeSeg();
    bindPostBehaviors(doc);
    setInterval(function () { applyRel(doc); }, 60000);
    if (window.matchMedia) {
      var mq = matchMedia("(prefers-color-scheme: dark)");
      var fire = function () { if (theme.get() === "system") doc.dispatchEvent(new CustomEvent("mo:theme", { detail: { theme: "system", resolved: theme.resolved() } })); };
      mq.addEventListener ? mq.addEventListener("change", fire) : mq.addListener(fire);
    }
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})();
