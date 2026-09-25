/* Candidate page (/<city>/<id>/): timeline load-more + filters, activity chart readout.
   Depends only on window.MO (shell.js). Data: /data/candidate/<id>/index.json + page-<n>.json. */
(function () {
  "use strict";
  var MO = window.MO;
  if (!MO) return;
  var STEP = 40;

  /* ---------- 30-day activity: hover / focus readout ---------- */
  function initActivity() {
    var list = MO.qs(".act-bars");
    var readout = MO.qs(".act-readout");
    if (!list || !readout) return;
    var days = MO.qsa(".act-day", list);
    var def = readout.getAttribute("data-default") || "";
    var active = -1;
    days.forEach(function (d) { d.removeAttribute("title"); });
    function show(i) {
      days.forEach(function (d, j) { d.classList.toggle("is-active", j === i); });
      active = i;
      if (i < 0) { readout.textContent = def; return; }
      var d = days[i];
      readout.textContent = "";
      var strong = document.createElement("strong");
      strong.textContent = Number(d.getAttribute("data-n") || 0).toLocaleString("zh-TW") + " 則";
      readout.appendChild(strong);
      readout.appendChild(document.createTextNode("・" + (d.getAttribute("data-label") || "")));
    }
    days.forEach(function (d, i) {
      d.addEventListener("pointerenter", function () { show(i); });
    });
    list.addEventListener("pointerleave", function () { if (document.activeElement !== list) show(-1); });
    list.addEventListener("focus", function () { show(active < 0 ? days.length - 1 : active); });
    list.addEventListener("blur", function () { show(-1); });
    list.addEventListener("keydown", function (ev) {
      var i = active < 0 ? days.length - 1 : active;
      if (ev.key === "ArrowLeft") i = Math.max(0, i - 1);
      else if (ev.key === "ArrowRight") i = Math.min(days.length - 1, i + 1);
      else if (ev.key === "Home") i = 0;
      else if (ev.key === "End") i = days.length - 1;
      else return;
      ev.preventDefault();
      show(i);
    });
  }

  /* ---------- timeline ---------- */
  function initTimeline() {
    var section = MO.qs(".cand-timeline");
    if (!section) return;
    var cid = section.getAttribute("data-candidate");
    var total = +section.getAttribute("data-count") || 0;
    var pages = +section.getAttribute("data-pages") || 1;
    var feed = MO.qs("#cand-feed", section);
    var more = MO.qs("[data-more]", section);
    var countEl = MO.qs(".cand-count", section);
    var emptyEl = MO.qs(".cand-empty", section);
    var form = MO.qs(".cand-filters", section);
    var clearTop = MO.qs(".cand-filters [data-clear]", section);
    var qInput = MO.qs("#cand-q", section);
    var base = "/data/candidate/" + encodeURIComponent(cid) + "/";

    var all = [];            // slim posts, newest first
    var loadedPages = 0;
    var shown = +section.getAttribute("data-ssr") || 0;
    var limit = shown;
    var busy = false;
    var auto = false;        // IntersectionObserver kicks in after the first manual 載入更多
    var state = { platform: "", intent: "", q: "", topics: [] };
    var byIdReady = MO.loadCandidates();

    function filtered() {
      return !!(state.platform || state.intent || state.q || state.topics.length);
    }
    function loadPage(n) {
      return MO.fetchJSON(base + "page-" + n + ".json").then(function (p) {
        all = all.concat(p.posts || []);
        loadedPages = n;
      });
    }
    function ensure(count) {   // load pages until `count` posts are available (Infinity = all)
      if (all.length >= count || loadedPages >= pages) return Promise.resolve();
      return loadPage(loadedPages + 1).then(function () { return ensure(count); });
    }
    function match(p) {
      if (state.platform && (p.platform || "website") !== state.platform) return false;
      if (state.intent && !(p.postingIntent && p.postingIntent.type === state.intent)) return false;
      if (state.topics.length) {
        var ts = p.topics || [];
        if (!state.topics.some(function (t) { return ts.indexOf(t) !== -1; })) return false;
      }
      if (state.q) {
        var hay = String(p.text || "").toLowerCase();
        var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
        if (!terms.every(function (t) { return hay.indexOf(t) !== -1; })) return false;
      }
      return true;
    }
    function list() { return filtered() ? all.filter(match) : all; }
    function listTotal(l) { return filtered() ? l.length : total; }

    function updateUI(l) {
      var n = listTotal(l);
      var visible = Math.min(shown, n);
      if (countEl) {
        countEl.textContent = filtered()
          ? "符合 " + n.toLocaleString("zh-TW") + " 則・顯示 " + visible.toLocaleString("zh-TW") + " 則"
          : "顯示最新 " + visible.toLocaleString("zh-TW") + " / " + total.toLocaleString("zh-TW") + " 則";
      }
      if (more) {
        more.hidden = visible >= n;
        more.disabled = busy;
        more.textContent = "載入更多";
      }
      if (emptyEl) emptyEl.hidden = !(filtered() && n === 0);
      if (clearTop) clearTop.hidden = !filtered();
    }

    function append(l, from, to) {
      var html = "";
      for (var i = from; i < Math.min(to, l.length); i++) html += MO.postHTML(l[i], { showCity: false });
      if (!html) return;
      var tmp = document.createElement("div");
      tmp.innerHTML = html;
      var frag = document.createDocumentFragment();
      var nodes = Array.prototype.slice.call(tmp.children);
      nodes.forEach(function (n) { frag.appendChild(n); });
      feed.appendChild(frag);
      nodes.forEach(function (n) { MO.bindPostBehaviors(n); });
    }

    function run(task) {
      if (busy) return Promise.resolve();
      busy = true;
      if (more) { more.disabled = true; more.setAttribute("aria-busy", "true"); }
      return Promise.all([byIdReady, task()]).catch(function () {
        MO.toast("無法取得貼文資料，請稍後再試");
      }).then(function () {
        busy = false;
        if (more) more.removeAttribute("aria-busy");
        updateUI(list());
      });
    }

    function loadMore() {
      return run(function () {
        limit = shown + STEP;
        return ensure(filtered() ? Infinity : limit).then(function () {
          return byIdReady;
        }).then(function () {
          var l = list();
          append(l, shown, limit);
          shown = Math.min(limit, l.length);
        });
      });
    }

    function rerender() {
      syncURL();
      return run(function () {
        return ensure(filtered() ? Infinity : STEP).then(function () {
          return byIdReady;
        }).then(function () {
          var l = list();
          feed.innerHTML = "";
          shown = 0;
          append(l, 0, STEP);
          shown = Math.min(STEP, l.length);
        });
      });
    }

    /* ---- controls ---- */
    function setPressed(group, attr, value) {
      MO.qsa("[" + attr + "]", group).forEach(function (b) {
        b.setAttribute("aria-pressed", b.getAttribute(attr) === value ? "true" : "false");
      });
    }
    var platGroup = MO.qs('[data-group="platform"]', form);
    var topicGroup = MO.qs('[data-group="topic"]', form);
    var intentSeg = MO.qs(".seg", form);

    function syncControls() {
      setPressed(platGroup, "data-platform", state.platform);
      setPressed(intentSeg, "data-intent", state.intent);
      MO.qsa("[data-topic]", topicGroup).forEach(function (b) {
        b.setAttribute("aria-pressed", state.topics.indexOf(b.getAttribute("data-topic")) !== -1 ? "true" : "false");
      });
      if (qInput.value !== state.q) qInput.value = state.q;
    }

    if (platGroup) platGroup.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-platform]");
      if (!b) return;
      state.platform = b.getAttribute("data-platform") || "";
      syncControls(); rerender();
    });
    if (intentSeg) intentSeg.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-intent]");
      if (!b) return;
      state.intent = b.getAttribute("data-intent") || "";
      syncControls(); rerender();
    });
    if (topicGroup) topicGroup.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-topic]");
      if (!b) return;
      var t = b.getAttribute("data-topic");
      var i = state.topics.indexOf(t);
      if (i === -1) state.topics.push(t); else state.topics.splice(i, 1);
      syncControls(); rerender();
    });
    var qTimer = null;
    qInput.addEventListener("input", function () {
      clearTimeout(qTimer);
      qTimer = setTimeout(function () {
        var v = qInput.value.trim();
        if (v === state.q) return;
        state.q = v; rerender();
      }, 250);
    });
    function clearAll(ev) {
      if (ev) ev.preventDefault();
      state = { platform: "", intent: "", q: "", topics: [] };
      syncControls(); rerender();
    }
    MO.qsa("[data-clear]", section).forEach(function (b) { b.addEventListener("click", clearAll); });
    form.addEventListener("reset", clearAll);

    if (more) more.addEventListener("click", function () { auto = true; loadMore(); });
    if (more && "IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        if (auto && !busy && !more.hidden && entries.some(function (e) { return e.isIntersecting; })) loadMore();
      }, { rootMargin: "600px 0px" }).observe(more);
    }

    /* ---- URL state (?platform=&intent=&topic=a,b&q=) ---- */
    function syncURL() {
      if (!window.history || !history.replaceState) return;
      var p = new URLSearchParams(location.search);
      ["platform", "intent", "topic", "q"].forEach(function (k) { p.delete(k); });
      if (state.platform) p.set("platform", state.platform);
      if (state.intent) p.set("intent", state.intent);
      if (state.topics.length) p.set("topic", state.topics.join(","));
      if (state.q) p.set("q", state.q);
      var s = p.toString();
      history.replaceState(null, "", location.pathname + (s ? "?" + s : "") + location.hash);
    }
    var params = new URLSearchParams(location.search);
    var known = {};
    MO.qsa("[data-topic]", topicGroup).forEach(function (b) { known[b.getAttribute("data-topic")] = true; });
    var slugToTopic = {};
    Object.keys(MO.TOPIC_SLUGS).forEach(function (t) { slugToTopic[MO.TOPIC_SLUGS[t]] = t; });
    state.platform = params.get("platform") || "";
    state.intent = MO.INTENT_LABELS[params.get("intent")] ? params.get("intent") : "";
    state.q = (params.get("q") || "").trim();
    state.topics = (params.get("topic") || "").split(",").map(function (t) {
      t = t.trim(); return slugToTopic[t] || t;
    }).filter(function (t) { return known[t]; });
    if (!MO.qs('[data-platform="' + state.platform.replace(/"/g, "") + '"]', platGroup)) state.platform = "";
    syncControls();
    if (filtered()) rerender(); else updateUI([]);
  }

  function init() { initActivity(); initTimeline(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
