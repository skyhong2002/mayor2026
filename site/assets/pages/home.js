/* `/` — feed deck behaviour: columns, per-column filters, add/remove, load more,
   story strip selection, URL params, phone city switcher. Depends on window.MO. */
(function () {
  "use strict";
  var MO = window.MO;
  var deckEl = document.getElementById("deck");
  var bootEl = document.getElementById("home-boot");
  if (!MO || !deckEl || !bootEl) return;

  var boot;
  try { boot = JSON.parse(bootEl.textContent); } catch (e) { return; }
  var qs = MO.qs, qsa = MO.qsa, esc = MO.esc;
  var byId = {};
  (boot.candidates || []).forEach(function (c) { byId[c.id] = c; });
  MO._byId = MO._byId || byId;
  var CITIES = boot.cities || MO.CITY_ORDER;
  var TOPICS = boot.topics || Object.keys(MO.TOPIC_SLUGS);
  var PER = boot.perCol || 30;
  var PLATFORMS = ["facebook", "instagram", "threads", "youtube", "x", "website", "podcast"];
  var INTENTS = [["", "全部"], ["self_initiated", "主動發文"], ["responsive", "回應他方觀點"]];
  var STORE = "moDeck";
  var phoneMQ = window.matchMedia ? matchMedia("(max-width: 699px)") : { matches: false };

  var addWrap = qs(".deck-add");
  var addBtn = addWrap && qs(".feed-col-add", addWrap);
  var addMenu = addWrap && qs(".addcol-menu", addWrap);
  var seg = qs(".deck-seg");
  var banner = qs(".deck-banner");
  var strip = qs(".story-strip");

  /* ---------------- column specs ---------------- */
  function emptyF() { return { c: [], p: [], t: [], n: "", q: "" }; }
  function validKey(k) {
    if (k === "all") return true;
    if (/^city:/.test(k)) return CITIES.indexOf(k.slice(5)) !== -1;
    if (/^cand:/.test(k)) return !!byId[k.slice(5)];
    return false;
  }
  function cleanF(f) {
    f = f || {};
    var arr = function (v, ok) { return (Array.isArray(v) ? v : []).filter(function (x) { return typeof x === "string" && ok(x); }); };
    return {
      c: arr(f.c, function (x) { return !!byId[x]; }),
      p: arr(f.p, function (x) { return PLATFORMS.indexOf(x) !== -1; }),
      t: arr(f.t, function (x) { return TOPICS.indexOf(x) !== -1; }),
      n: f.n === "self_initiated" || f.n === "responsive" ? f.n : "",
      q: typeof f.q === "string" ? f.q.slice(0, 80) : ""
    };
  }
  function spec(k, f) { return { k: k, f: cleanF(f) }; }
  function defaultCols() { return CITIES.map(function (c) { return spec("city:" + c); }); }
  function isFiltered(f) { return !!(f.c.length || f.p.length || f.t.length || f.n || f.q.trim()); }
  function cityLabel(c, short) { var s = MO.CITY_SHORT[c] || c; return short ? s : s + "市"; }
  function colTitle(k) {
    if (k === "all") return "全部城市";
    if (/^city:/.test(k)) return cityLabel(k.slice(5));
    var c = byId[k.slice(5)] || {};
    return c.name || k.slice(5);
  }
  function colCandidates(k) {
    if (k === "all") return boot.candidates;
    if (/^city:/.test(k)) { var city = k.slice(5); return boot.candidates.filter(function (c) { return c.city === city; }); }
    return [];
  }
  function bundleURL(k) {
    var name = k === "all" ? "all" : /^city:/.test(k) ? k.slice(5) : "c/" + k.slice(5);
    return "/data/feed/" + name + ".json?v=" + (boot.v || "");
  }

  /* ---------------- state ---------------- */
  var saved = readSaved();
  var state = { cols: saved.cols, m: saved.m, transient: false };

  function readSaved() {
    var out = { cols: defaultCols(), m: "all" };
    try {
      var raw = JSON.parse(localStorage.getItem(STORE) || "null");
      if (raw && Array.isArray(raw.cols)) {
        var seen = {};
        var cols = raw.cols.filter(function (c) {
          if (!c || !validKey(c.k) || seen[c.k]) return false;
          seen[c.k] = 1; return true;
        }).map(function (c) { return spec(c.k, c.f); });
        if (cols.length) out.cols = cols;
      }
      if (raw && validKey(raw.m)) out.m = raw.m;
    } catch (e) { /* ignore corrupt storage */ }
    return out;
  }
  function save() {
    if (state.transient) return;
    saved = { cols: state.cols, m: state.m };
    try { localStorage.setItem(STORE, JSON.stringify({ v: 1, cols: state.cols, m: state.m })); } catch (e) { /* private mode */ }
  }

  function listParam(p, name) {
    return p.getAll(name).join(",").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
  }
  function fromURL() {
    var p = new URLSearchParams(location.search);
    var f = emptyF();
    listParam(p, "platform").forEach(function (v) { v = v.toLowerCase(); if (PLATFORMS.indexOf(v) !== -1) f.p.push(v); });
    var slugTopic = {};
    Object.keys(MO.TOPIC_SLUGS).forEach(function (t) { slugTopic[MO.TOPIC_SLUGS[t]] = t; });
    listParam(p, "topic").forEach(function (v) { var t = slugTopic[v] || v; if (TOPICS.indexOf(t) !== -1) f.t.push(t); });
    var intent = (p.get("intent") || "").trim();
    if (intent === "responsive" || intent === "self_initiated") f.n = intent;
    else if (intent === "self") f.n = "self_initiated";
    f.q = (p.get("q") || "").trim();
    var cand = (p.get("candidate") || "").trim();
    var city = (p.get("city") || "").trim();
    var hasF = isFiltered(f);
    if (cand && byId[cand]) return { cols: [spec("cand:" + cand, f)], candidate: cand };
    if (city === "all" || CITIES.indexOf(city) !== -1) {
      return { cols: [spec(city === "all" ? "all" : "city:" + city, f)], city: city };
    }
    if (hasF) return { cols: saved.cols.map(function (c) { return spec(c.k, f); }) };
    return null;
  }

  /* ---------------- column DOM ---------------- */
  function uid(k) { return k.replace(/[^a-z0-9-]/gi, "-"); }
  function headMark(k) {
    if (/^cand:/.test(k)) { var c = byId[k.slice(5)]; if (c) return MO.avatarHTML(c, "xs", null, "feed-col-avatar"); }
    return '<span class="feed-col-dot" aria-hidden="true"></span>';
  }
  function colShell(s) {
    var id = uid(s.k), title = colTitle(s.k);
    var cityAttr = /^city:/.test(s.k) ? ' data-city="' + esc(s.k.slice(5)) + '"' : "";
    var sub = /^cand:/.test(s.k) && byId[s.k.slice(5)] ? '<span class="feed-col-sub">' + esc(cityLabel(byId[s.k.slice(5)].city, true)) + "</span>" : "";
    var el = document.createElement("section");
    el.className = "feed-col";
    el.setAttribute("data-col", s.k);
    if (cityAttr) el.setAttribute("data-city", s.k.slice(5));
    el.setAttribute("aria-labelledby", "col-" + id + "-t");
    el.innerHTML =
      '<header class="feed-col-head">' + headMark(s.k) +
      '<h2 class="feed-col-title" id="col-' + id + '-t">' + esc(title) + sub + "</h2>" +
      '<span class="feed-col-count" aria-live="polite"></span>' +
      '<div class="feed-col-tools">' +
      '<button class="col-btn" type="button" data-act="filter" aria-expanded="false" aria-controls="col-' + id + '-f">' + MO.icon("filter") + '<span class="col-btn-label">篩選</span></button>' +
      '<button class="col-btn" type="button" data-act="remove" aria-label="移除「' + esc(title) + '」欄">' + MO.icon("close") + "</button>" +
      "</div></header>" +
      '<div class="col-filters" id="col-' + id + '-f" hidden></div>' +
      '<div class="col-body" tabindex="-1"></div>';
    el._sig = null;
    return el;
  }
  function sigOf(f) { return JSON.stringify([f.c, f.p, f.t, f.n, f.q.trim().toLowerCase()]); }

  function adoptSSR(el) {
    if (el._adopted) return;
    el._adopted = true;
    el._sig = sigOf(emptyF());
    el._shown = qsa(".feed-post", qs(".col-body", el)).length;
    var tools = qs(".feed-col-tools", el);
    if (tools) tools.hidden = false;
  }

  function specOf(el) {
    var k = el.getAttribute("data-col");
    for (var i = 0; i < state.cols.length; i++) if (state.cols[i].k === k) return state.cols[i];
    return el._phoneSpec || null;
  }

  /* ---------------- rendering the deck ---------------- */
  function phoneKey() { return state.transient ? state.cols[0].k : state.m; }

  function renderDeck() {
    var list = state.cols.slice();
    var pk = phoneKey();
    var phoneOnly = null;
    if (!list.some(function (c) { return c.k === pk; })) { phoneOnly = spec(pk); list.push(phoneOnly); }

    var existing = {};
    qsa(".feed-col", deckEl).forEach(function (el) { existing[el.getAttribute("data-col")] = el; });
    var keep = {};
    list.forEach(function (s) {
      var el = existing[s.k];
      if (el) adoptSSR(el); else el = colShell(s);
      el._phoneSpec = s === phoneOnly ? s : null;
      el.classList.toggle("is-phone-only", s === phoneOnly);
      el.classList.toggle("is-active", s.k === pk);
      deckEl.insertBefore(el, addWrap);
      keep[s.k] = el;
      syncCol(el, s);
    });
    Object.keys(existing).forEach(function (k) { if (!keep[k]) existing[k].remove(); });
    var single = state.cols.length <= 1;
    qsa('.feed-col [data-act="remove"]', deckEl).forEach(function (b) {
      var own = b.closest(".feed-col");
      b.hidden = single || own.classList.contains("is-phone-only") || state.transient;
    });
    deckEl.classList.toggle("is-single", state.cols.length === 1);
    if (addWrap) addWrap.hidden = state.transient;
    syncSeg();
    syncStrip();
    syncBanner();
  }

  function syncCol(el, s) {
    var filtered = isFiltered(s.f);
    var fb = qs('[data-act="filter"]', el);
    if (fb) {
      fb.classList.toggle("is-active", filtered);
      var lab = qs(".col-btn-label", fb);
      if (lab) lab.textContent = filtered ? "已篩選" : "篩選";
    }
    var sig = sigOf(s.f);
    if (el._sig !== sig) { el._sig = sig; fill(el, s); }
  }

  /* ---------------- data + cards ---------------- */
  function matcher(f) {
    var terms = f.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return function (p) {
      if (f.c.length && f.c.indexOf(p.candidateId) === -1) return false;
      if (f.p.length && f.p.indexOf(p.platform) === -1) return false;
      if (f.t.length && !(p.topics || []).some(function (t) { return f.t.indexOf(t) !== -1; })) return false;
      if (f.n && !(p.postingIntent && p.postingIntent.type === f.n)) return false;
      if (terms.length) {
        var c = byId[p.candidateId] || {};
        var hay = ((p.text || "") + " " + (c.name || "")).toLowerCase();
        for (var i = 0; i < terms.length; i++) if (hay.indexOf(terms[i]) === -1) return false;
      }
      return true;
    };
  }
  function ctxFor(k) { return { byId: byId, showCity: !/^(city|cand):/.test(k) }; }

  function setBusy(el, on) {
    var body = qs(".col-body", el);
    body.setAttribute("aria-busy", on ? "true" : "false");
    el.classList.toggle("is-busy", on);
    var more = qs('[data-act="more"]', body);
    if (more) { more.disabled = on; more.textContent = on ? "正在取得貼文…" : "載入更多"; }
  }

  function getList(el, s) {
    return MO.fetchJSON(bundleURL(s.k)).then(function (b) {
      el._bundle = b;
      el._list = (b.posts || []).filter(matcher(s.f));
      return el._list;
    });
  }

  function fill(el, s) {
    var body = qs(".col-body", el);
    var token = el._token = (el._token || 0) + 1;
    el._shown = 0;
    setBusy(el, true);
    getList(el, s).then(function (list) {
      if (token !== el._token) return;
      body.innerHTML = "";
      el._shown = 0;
      appendCards(el, s, list);
      setBusy(el, false);
      updateCount(el, s);
    }, function () {
      if (token !== el._token) return;
      setBusy(el, false);
      showError(el);
    });
  }

  function loadMore(el) {
    var s = specOf(el);
    if (!s || el.classList.contains("is-busy")) return;
    if (el._list) { appendCards(el, s, el._list); return; }
    var token = el._token = (el._token || 0) + 1;
    setBusy(el, true);
    getList(el, s).then(function (list) {
      if (token !== el._token) return;
      setBusy(el, false);
      appendCards(el, s, list);
      updateCount(el, s);
    }, function () {
      if (token !== el._token) return;
      setBusy(el, false);
      showError(el);
    });
  }

  function appendCards(el, s, list) {
    var body = qs(".col-body", el);
    qsa(".feed-more, .col-end, .col-error", body).forEach(function (n) { n.remove(); });
    var have = {};
    qsa(".feed-post", body).forEach(function (a) { have[a.getAttribute("data-id")] = 1; });
    var ctx = ctxFor(s.k);
    var html = "", added = 0, i = el._shown || 0;
    for (; i < list.length && added < PER; i++) {
      if (have[list[i].id]) continue;
      html += MO.postHTML(list[i], ctx);
      added++;
    }
    el._shown = i;
    var frag = document.createElement("div");
    frag.innerHTML = html;
    var first = frag.firstElementChild;
    while (frag.firstChild) body.appendChild(frag.firstChild);
    if (!qs(".feed-post", body)) {
      body.insertAdjacentHTML("beforeend", emptyHTML(s));
    } else if (i < list.length) {
      body.insertAdjacentHTML("beforeend", '<div class="feed-more"><button class="btn btn-sm" type="button" data-act="more">載入更多</button></div>');
      observe(el);
    } else {
      body.insertAdjacentHTML("beforeend", endHTML(el, s));
    }
    MO.bindPostBehaviors(body);
    return first;
  }

  function emptyHTML(s) {
    var filtered = isFiltered(s.f);
    return '<div class="empty"><p class="empty-title">' + (filtered ? "沒有符合篩選條件的貼文" : "這一欄尚無貼文") + "</p>" +
      '<p class="empty-body">' + (filtered ? "篩選只涵蓋這一欄最新 " + (boot.bundle || 400) + " 則貼文。試著移除部分條件，或改用全站搜尋。" : "候選人發文後會出現在這裡。") + "</p>" +
      (filtered ? '<button class="btn btn-sm" type="button" data-act="clear">清除篩選</button>' : "") + "</div>";
  }
  function endHTML(el, s) {
    var b = el._bundle || {};
    var truncated = (b.total || 0) > (b.count || 0);
    var link = /^cand:/.test(s.k) && byId[s.k.slice(5)]
      ? "/" + byId[s.k.slice(5)].city + "/" + s.k.slice(5) + "/"
      : "/search/" + (s.f.q.trim() ? "?q=" + encodeURIComponent(s.f.q.trim()) : "");
    var txt = truncated
      ? "這一欄只提供最新 " + (b.count || 0) + " 則貼文" + (isFiltered(s.f) ? "（篩選也只在其中進行）" : "") + "。"
      : "已經到底了。";
    return '<p class="col-end">' + esc(txt) + (truncated ? ' <a href="' + esc(link) + '">' + (/^cand:/.test(s.k) ? "看候選人頁的完整時間軸" : "用全站搜尋找更早的貼文") + "</a>" : "") + "</p>";
  }
  function showError(el) {
    var body = qs(".col-body", el);
    qsa(".feed-more, .col-error", body).forEach(function (n) { n.remove(); });
    body.insertAdjacentHTML("beforeend",
      '<div class="empty col-error"><p class="empty-title">無法取得貼文</p><p class="empty-body">網路連線可能中斷，或資料正在更新。請稍後再試。</p>' +
      '<button class="btn btn-sm" type="button" data-act="retry">重試</button></div>');
  }
  function updateCount(el, s) {
    var out = qs(".feed-col-count", el);
    if (!out) return;
    out.textContent = isFiltered(s.f) && el._list ? el._list.length + " 則" : "";
  }

  var io = "IntersectionObserver" in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      var col = e.target.closest(".feed-col");
      if (col && e.target.isConnected) loadMore(col);
    });
  }, { rootMargin: "0px 0px 480px 0px" }) : null;
  function observe(el) {
    if (!io) return;
    var m = qs(".col-body > .feed-more", el);
    if (m) io.observe(m);
  }

  /* ---------------- filter panel ---------------- */
  function chipBtn(label, fk, fv, pressed, extra) {
    return '<button class="chip' + (extra && extra.cls ? " " + extra.cls : "") + '" type="button" data-fk="' + fk + '" data-fv="' + esc(fv) + '" aria-pressed="' + (pressed ? "true" : "false") + '"' +
      (extra && extra.party ? ' data-party="' + extra.party + '"' : "") + ">" + (extra && extra.icon ? MO.icon(extra.icon) : "") + "<span>" + esc(label) + "</span></button>";
  }
  function buildFilters(el, s) {
    var panel = qs(".col-filters", el);
    var id = uid(s.k);
    var f = s.f;
    var rows = '<div class="cf-q"><label class="sr-only" for="cf-q-' + id + '">以關鍵字篩選這一欄</label>' +
      '<input class="input" id="cf-q-' + id + '" type="search" enterkeyhint="search" autocomplete="off" placeholder="關鍵字（內文、候選人）" value="' + esc(f.q) + '"></div>';
    var cands = colCandidates(s.k);
    if (cands.length > 1) {
      rows += row("候選人", cands.map(function (c) {
        return chipBtn(c.name, "c", c.id, f.c.indexOf(c.id) !== -1, { cls: "chip-party", party: MO.partySlug(c.party) });
      }).join(""));
    }
    rows += row("平台", PLATFORMS.map(function (p) {
      return chipBtn(MO.PLATFORM_LABELS[p] || p, "p", p, f.p.indexOf(p) !== -1, { icon: p });
    }).join(""));
    rows += row("議題", TOPICS.map(function (t) { return chipBtn(t, "t", t, f.t.indexOf(t) !== -1); }).join(""));
    rows += '<div class="filter-row"><span class="filter-label">動機</span><div class="seg" role="group" aria-label="發文動機">' +
      INTENTS.map(function (it) {
        return '<button type="button" data-fk="n" data-fv="' + it[0] + '" aria-pressed="' + (f.n === it[0] ? "true" : "false") + '">' + esc(it[1]) + "</button>";
      }).join("") + "</div></div>";
    rows += '<div class="cf-foot"><p class="xs muted">篩選範圍：這一欄最新 ' + (boot.bundle || 400) + ' 則貼文。</p>' +
      '<button class="btn btn-sm btn-ghost" type="button" data-act="clear"' + (isFiltered(f) ? "" : " disabled") + ">清除篩選</button></div>";
    panel.innerHTML = rows;
    function row(label, chips) {
      return '<div class="filter-row"><span class="filter-label">' + label + '</span><div class="chips">' + chips + "</div></div>";
    }
  }
  function openFilters(el, open) {
    var s = specOf(el);
    var panel = qs(".col-filters", el);
    var btn = qs('[data-act="filter"]', el);
    if (!s || !panel || !btn) return;
    if (open == null) open = panel.hidden;
    if (open) buildFilters(el, s);
    panel.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { var inp = qs("input", panel); if (inp && !phoneMQ.matches) inp.focus({ preventScroll: true }); }
  }
  function applyFilter(el, s) {
    save();
    syncCol(el, s);
    var clear = qs('.col-filters [data-act="clear"]', el);
    if (clear) clear.disabled = !isFiltered(s.f);
    var body = qs(".col-body", el);
    if (body) body.scrollTop = 0;
  }

  /* ---------------- add-column menu ---------------- */
  function buildAddMenu() {
    var present = {};
    state.cols.forEach(function (c) { present[c.k] = 1; });
    var btn = function (k, label, mark) {
      return '<button type="button" data-add="' + esc(k) + '">' + (mark || "") + "<span>" + esc(label) + "</span></button>";
    };
    var html = '<div class="addcol-head"><p class="addcol-title">加入欄位</p><button class="col-btn" type="button" data-act="add-close" aria-label="關閉">' + MO.icon("close") + "</button></div>";
    var cityBtns = CITIES.filter(function (c) { return !present["city:" + c]; }).map(function (c) {
      return btn("city:" + c, cityLabel(c), '<span class="feed-col-dot" data-city="' + c + '" aria-hidden="true"></span>');
    });
    if (!present.all) cityBtns.unshift(btn("all", "全部城市", '<span class="feed-col-dot" aria-hidden="true"></span>'));
    if (cityBtns.length) html += '<p class="addcol-label">城市</p>' + cityBtns.join("");
    var candBtns = boot.candidates.filter(function (c) { return !present["cand:" + c.id]; }).map(function (c) {
      return btn("cand:" + c.id, c.name + "・" + cityLabel(c.city, true), MO.avatarHTML(c, "xs"));
    });
    if (candBtns.length) html += '<p class="addcol-label">單一候選人</p>' + candBtns.join("");
    html += '<div class="addcol-sep"></div><button type="button" data-act="reset-deck"><span>恢復預設六欄</span></button>';
    addMenu.innerHTML = html;
  }
  function toggleAdd(open) {
    if (!addMenu) return;
    if (open) buildAddMenu();
    addMenu.hidden = !open;
    addBtn.hidden = open;
    addBtn.setAttribute("aria-expanded", open ? "true" : "false");
    addWrap.classList.toggle("is-open", open);
    if (open) { var f = qs("[data-add], [data-act=reset-deck]", addMenu); if (f) f.focus({ preventScroll: true }); addWrap.scrollIntoView({ inline: "end", block: "nearest" }); }
    else addBtn.focus({ preventScroll: true });
  }

  /* ---------------- chrome: seg, strip, banner ---------------- */
  function syncSeg() {
    if (!seg) return;
    seg.hidden = false;
    var pk = phoneKey();
    qsa("[data-mcol]", seg).forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-mcol") === pk ? "true" : "false"); });
  }
  function syncStrip() {
    if (!strip) return;
    var sel = state.transient && /^cand:/.test(state.cols[0].k) && state.cols.length === 1 ? state.cols[0].k.slice(5) : "";
    strip.classList.toggle("has-selection", !!sel);
    qsa(".story-item", strip).forEach(function (a) {
      var on = a.getAttribute("data-candidate") === sel;
      if (on) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current");
    });
  }
  function syncBanner() {
    if (!banner) return;
    if (!state.transient) { banner.hidden = true; banner.innerHTML = ""; return; }
    var s = state.cols[0];
    var what = state.cols.length === 1 ? "「" + colTitle(s.k) + "」" : "套用網址篩選的河道";
    banner.innerHTML = MO.icon("filter") + "<p>正在檢視" + esc(what) + "，這個檢視不會改動你儲存的欄位。" +
      ' <a href="/" data-act="home">回到我的欄位</a></p>';
    banner.hidden = false;
  }

  function applyURL() {
    var u = fromURL();
    qsa(".col-filters", deckEl).forEach(function (p) { p.hidden = true; });
    if (u) { state.cols = u.cols; state.transient = true; }
    else { state.cols = saved.cols; state.m = saved.m; state.transient = false; }
    renderDeck();
    deckEl.scrollLeft = 0;
  }
  function go(url) {
    history.pushState(null, "", url);
    applyURL();
    if (phoneMQ.matches) window.scrollTo({ top: 0 });
  }

  /* ---------------- events ---------------- */
  var qTimer = null;
  deckEl.addEventListener("click", function (ev) {
    var t = ev.target;
    var colEl = t.closest(".feed-col");
    var act = t.closest("[data-act]");
    var a = act && act.getAttribute("data-act");
    if (colEl) {
      var s = specOf(colEl);
      if (a === "filter") { openFilters(colEl); return; }
      if (a === "remove" && s) {
        state.cols = state.cols.filter(function (c) { return c.k !== s.k; });
        if (state.m === s.k) state.m = "all";
        save(); renderDeck();
        if (addBtn && !addWrap.hidden) addBtn.focus({ preventScroll: true });
        return;
      }
      if (a === "more") { loadMore(colEl); return; }
      if (a === "retry" && s) { colEl._list = null; if (colEl._sig === sigOf(s.f) && !qs(".feed-post", colEl)) fill(colEl, s); else loadMore(colEl); return; }
      if (a === "clear" && s) { s.f = emptyF(); if (!qs(".col-filters", colEl).hidden) buildFilters(colEl, s); applyFilter(colEl, s); return; }
      var chip = t.closest("[data-fk]");
      if (chip && s) {
        var fk = chip.getAttribute("data-fk"), fv = chip.getAttribute("data-fv");
        if (fk === "n") {
          s.f.n = fv;
          qsa('[data-fk="n"]', colEl).forEach(function (b) { b.setAttribute("aria-pressed", b === chip ? "true" : "false"); });
        } else {
          var arr = s.f[fk], i = arr.indexOf(fv);
          if (i === -1) arr.push(fv); else arr.splice(i, 1);
          chip.setAttribute("aria-pressed", i === -1 ? "true" : "false");
        }
        applyFilter(colEl, s);
      }
      return;
    }
    if (!addWrap || !addWrap.contains(t)) return;
    if (t.closest(".feed-col-add")) { toggleAdd(true); return; }
    if (a === "add-close") { toggleAdd(false); return; }
    if (a === "reset-deck") { state.cols = defaultCols(); state.m = "all"; save(); toggleAdd(false); renderDeck(); deckEl.scrollLeft = 0; return; }
    var add = t.closest("[data-add]");
    if (add) {
      var k = add.getAttribute("data-add");
      if (!validKey(k)) return;
      state.cols.push(spec(k));
      save();
      toggleAdd(false);
      renderDeck();
      var el = qs('.feed-col[data-col="' + k + '"]', deckEl);
      if (el) { el.scrollIntoView({ inline: "nearest", block: "nearest", behavior: "smooth" }); var h = qs(".col-body", el); if (h) h.focus({ preventScroll: true }); }
    }
  });
  deckEl.addEventListener("input", function (ev) {
    var inp = ev.target.closest(".cf-q input");
    if (!inp) return;
    var colEl = inp.closest(".feed-col");
    var s = specOf(colEl);
    clearTimeout(qTimer);
    qTimer = setTimeout(function () { s.f.q = inp.value.slice(0, 80); applyFilter(colEl, s); }, 200);
  });
  deckEl.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var panel = ev.target.closest(".col-filters");
    if (panel) { var colEl = panel.closest(".feed-col"); openFilters(colEl, false); qs('[data-act="filter"]', colEl).focus(); return; }
    if (addMenu && addMenu.contains(ev.target)) toggleAdd(false);
  });
  document.addEventListener("click", function (ev) {
    if (addMenu && !addMenu.hidden && !addWrap.contains(ev.target)) { addMenu.hidden = true; addBtn.hidden = false; addBtn.setAttribute("aria-expanded", "false"); addWrap.classList.remove("is-open"); }
  });

  if (strip) strip.addEventListener("click", function (ev) {
    var a = ev.target.closest(".story-item");
    if (!a || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.button > 0) return;
    ev.preventDefault();
    var id = a.getAttribute("data-candidate");
    go(a.getAttribute("aria-current") === "true" ? "/" : "/?candidate=" + encodeURIComponent(id));
  });
  if (seg) seg.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-mcol]");
    if (!b) return;
    var k = b.getAttribute("data-mcol");
    state.m = k;
    if (state.transient) { history.pushState(null, "", "/"); state.cols = saved.cols; state.transient = false; }
    save();
    renderDeck();
    window.scrollTo({ top: 0 });
  });
  if (banner) banner.addEventListener("click", function (ev) {
    if (ev.target.closest('[data-act="home"]')) { ev.preventDefault(); go("/"); }
  });
  window.addEventListener("popstate", applyURL);

  qsa(".feed-col", deckEl).forEach(function (el) { adoptSSR(el); observe(el); });
  applyURL();
})();
