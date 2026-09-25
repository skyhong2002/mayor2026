/* /spectrum/ 熱圖互動 ＋ /spectrum/<slug>/ 候選人篩選與貼文續載。依賴 window.MO（shell.js）。 */
(function () {
  "use strict";
  var MO = window.MO;
  var doc = document;
  if (!MO) return;
  var esc = MO.esc;

  /* ======================================================================
     shared helpers (keep pct / step in sync with scripts/render/spectrum.py)
     ====================================================================== */
  function pct(v) {
    if (!(v > 0)) return "0%";
    if (v < 0.005) return "<1%";
    return Math.floor(v * 100 + 0.5) + "%";
  }
  function fmtN(n) { return Number(n || 0).toLocaleString("en-US"); }
  function topicHref(t) { return "/spectrum/" + (MO.TOPIC_SLUGS[t] || "life") + "/"; }

  /* ======================================================================
     /spectrum/
     ====================================================================== */
  function initIndex() {
    var bootEl = doc.getElementById("spectrum-boot");
    var view = MO.qs(".spectrum-view");
    if (!bootEl || !view) return;
    var boot = JSON.parse(bootEl.textContent);
    var bins = boot.bins;
    var cands = boot.candidates;
    var result = boot.initial;
    var controls = MO.qs(".spectrum-controls");
    var statusEl = MO.qs(".spectrum-status");
    var resultWrap = MO.qs(".spectrum-result");

    var SORTS = {
      latest: function (a, b) { return tsOf(cands[b].latestPostAt) - tsOf(cands[a].latestPostAt); },
      count: function (a, b) { return (cands[b].postCount || 0) - (cands[a].postCount || 0); }
    };
    var state = {
      range: 0,
      excluded: {},
      excludedIntents: {},
      sort: Math.random() < 0.5 ? "latest" : "count"
    };
    state.excluded[boot.fallback] = true;

    var indexPosts = null;
    var indexPromise = null;
    var pending = 0;

    function tsOf(v) { var t = v ? Date.parse(v) : NaN; return isNaN(t) ? 0 : t; }
    function step(v) {
      if (!(v > 0)) return 0;
      var s = 1;
      for (var i = 0; i < bins.length; i++) if (v >= bins[i]) s++;
      return s;
    }

    function compute() {
      var cutoff = state.range ? Date.now() - state.range * 86400000 : null;
      var per = {};
      var intentCounts = {};
      indexPosts.forEach(function (post) {
        var intent = post.postingIntent || "self_initiated";
        if (cutoff) {
          var at = tsOf(post.postedAt);
          if (!at || at < cutoff) return;
        }
        intentCounts[intent] = (intentCounts[intent] || 0) + 1;
        if (state.excludedIntents[intent]) return;
        var bucket = per[post.candidateId] || (per[post.candidateId] = { totals: {}, count: 0 });
        var counted = false;
        var scores = post.topicScores || {};
        Object.keys(scores).forEach(function (topic) {
          if (state.excluded[topic]) return;
          bucket.totals[topic] = (bucket.totals[topic] || 0) + (+scores[topic] || 0);
          counted = true;
        });
        if (counted) bucket.count += 1;
      });
      var out = {};
      Object.keys(per).forEach(function (cid) {
        var b = per[cid];
        var grand = 0;
        Object.keys(b.totals).forEach(function (t) { grand += b.totals[t]; });
        var props = {};
        if (grand > 0) Object.keys(b.totals).forEach(function (t) { props[t] = b.totals[t] / grand; });
        out[cid] = { props: props, count: b.count };
      });
      return { result: out, intentCounts: intentCounts };
    }

    function columns(res) {
      var totals = {};
      Object.keys(res).forEach(function (cid) {
        var p = res[cid].props;
        Object.keys(p).forEach(function (t) { totals[t] = (totals[t] || 0) + p[t]; });
      });
      return Object.keys(totals).filter(function (t) { return totals[t] > 0; }).sort(function (a, b) {
        return totals[b] - totals[a] || boot.topics.indexOf(a) - boot.topics.indexOf(b);
      });
    }

    function identity(c, count) {
      return '<a class="spectrum-identity" href="/' + esc(c.city) + "/" + esc(c.id) + '/">' + MO.avatarHTML(c, "sm") +
        '<span class="spectrum-who-text"><strong>' + esc(c.name) + '</strong><span class="spectrum-who-meta">' +
        esc(c.party || "無黨籍") + " · " + fmtN(count) + " 則</span></span></a>";
    }

    function ordered(ids) { return ids.filter(function (id) { return cands[id]; }).sort(SORTS[state.sort]); }
    function cityLabel(id) { return (MO.CITY_SHORT[id] || id) + "市"; }

    function tableHTML(res, topics) {
      var head = topics.map(function (t) {
        return '<th scope="col" class="spectrum-topic"><a href="' + topicHref(t) + '" title="看「' + esc(t) + '」議題的跨候選人比較">' + esc(t) + "</a></th>";
      }).join("");
      var rows = "";
      boot.cities.forEach(function (city) {
        var ids = ordered(city.candidateIds);
        if (!ids.length) return;
        rows += '<tr class="spectrum-city-row"><th colspan="' + (topics.length + 1) + '" scope="rowgroup"><span class="spectrum-city-label chip-city" data-city="' +
          esc(city.id) + '">' + esc(cityLabel(city.id)) + "</span></th></tr>";
        ids.forEach(function (cid) {
          var c = cands[cid];
          var entry = res[cid] || { props: {}, count: 0 };
          var props = entry.props;
          var keys = Object.keys(props);
          var rowMax = 0;
          keys.forEach(function (t) { if (props[t] > rowMax) rowMax = props[t]; });
          var cells = topics.map(function (t) {
            if (!keys.length) return '<td class="spectrum-cell" data-step="0"><span aria-label="無資料">—</span></td>';
            var v = props[t] || 0;
            var isMax = v > 0 && v === rowMax;
            var title = c.name + "｜" + t + " " + pct(v) + (isMax ? "（最高）" : "");
            return '<td class="spectrum-cell' + (isMax ? " spectrum-cell-max" : "") + '" data-step="' + step(v) + '" title="' + esc(title) + '">' +
              (v > 0 ? pct(v) : "·") + "</td>";
          }).join("");
          rows += '<tr data-candidate="' + esc(cid) + '"><th scope="row" class="spectrum-who">' + identity(c, entry.count) + "</th>" + cells + "</tr>";
        });
      });
      return '<div class="spectrum-scroll" tabindex="0" role="region" aria-label="議題光譜熱圖（可橫向捲動）">' +
        '<table class="spectrum-table"><caption class="sr-only">各候選人議題發文比例</caption>' +
        '<thead><tr><th scope="col" class="spectrum-who-head">候選人</th>' + head + "</tr></thead><tbody>" + rows + "</tbody></table></div>";
    }

    function cardsHTML(res) {
      var out = "";
      boot.cities.forEach(function (city) {
        var ids = ordered(city.candidateIds);
        if (!ids.length) return;
        var cards = ids.map(function (cid) {
          var c = cands[cid];
          var entry = res[cid] || { props: {}, count: 0 };
          var top = Object.keys(entry.props).map(function (t) { return [t, entry.props[t]]; })
            .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 5);
          var meters = top.length ? top.map(function (tv, i) {
            return '<div class="meter-row' + (i === 0 ? " is-max" : "") + '"><a class="meter-label" href="' + topicHref(tv[0]) + '">' + esc(tv[0]) + "</a>" +
              '<div class="meter" role="img" aria-label="' + esc(tv[0]) + " " + pct(tv[1]) + '"><span class="meter-fill" style="--v:' + tv[1].toFixed(4) + '"></span></div>' +
              '<span class="meter-value">' + pct(tv[1]) + "</span></div>";
          }).join("") : '<p class="spectrum-card-empty">目前的篩選條件下沒有議題貼文。</p>';
          return '<article class="card spectrum-card" data-candidate="' + esc(cid) + '">' + identity(c, entry.count) +
            '<div class="spectrum-card-meters">' + meters + "</div></article>";
        }).join("");
        out += '<section class="spectrum-card-city"><h2 class="spectrum-card-city-title chip-city" data-city="' + esc(city.id) + '">' +
          esc(cityLabel(city.id)) + "</h2>" + cards + "</section>";
      });
      return '<div class="spectrum-cards">' + out + "</div>";
    }

    function render() {
      var topics = columns(result);
      var scroller = MO.qs(".spectrum-scroll", view);
      var scrollLeft = scroller ? scroller.scrollLeft : 0;
      if (!topics.length) {
        view.innerHTML = '<div class="empty"><p class="empty-title">目前的篩選條件下沒有任何議題資料</p>' +
          '<p class="empty-body">試著放寬時間範圍，或恢復部分議題與發文動機。</p></div>';
        return;
      }
      view.innerHTML = tableHTML(result, topics) + cardsHTML(result);
      scroller = MO.qs(".spectrum-scroll", view);
      if (scroller) scroller.scrollLeft = scrollLeft;
    }

    function syncControls(intentCounts) {
      MO.qsa("[data-control=range] button", controls).forEach(function (b) {
        b.setAttribute("aria-pressed", String(+b.getAttribute("data-range") === state.range));
      });
      MO.qsa("[data-control=sort] button", controls).forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-sort") === state.sort));
      });
      MO.qsa("[data-topic]", controls).forEach(function (b) {
        var off = !!state.excluded[b.getAttribute("data-topic")];
        b.setAttribute("aria-pressed", String(!off));
        b.title = off ? "已排除，點擊恢復" : "點擊排除";
      });
      MO.qsa("[data-intent]", controls).forEach(function (b) {
        var k = b.getAttribute("data-intent");
        var off = !!state.excludedIntents[k];
        b.setAttribute("aria-pressed", String(!off));
        b.title = off ? "已排除，點擊恢復" : "點擊排除";
        if (intentCounts) {
          var cnt = MO.qs(".chip-count", b);
          if (cnt) cnt.textContent = fmtN(intentCounts[k] || 0);
        }
      });
    }

    function setStatus(html, busy) {
      if (!statusEl) return;
      if (!html) { statusEl.hidden = true; statusEl.innerHTML = ""; } else { statusEl.hidden = false; statusEl.innerHTML = html; }
      if (resultWrap) resultWrap.classList.toggle("is-busy", !!busy);
    }

    function loadIndex() {
      if (indexPromise) return indexPromise;
      setStatus('<progress max="100"></progress><span>正在下載完整議題索引（約 1.4 MB）以重新計算…</span>', true);
      var bar = MO.qs("progress", statusEl);
      var label = MO.qs("span", statusEl);
      indexPromise = fetch("/api/topic-index.json", { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        var total = +r.headers.get("content-length") || 0;
        if (!r.body || !r.body.getReader || !window.TextDecoder || !total) return r.json();
        var reader = r.body.getReader();
        var chunks = [];
        var got = 0;
        function pump() {
          return reader.read().then(function (res) {
            if (res.done) return;
            chunks.push(res.value);
            got += res.value.length;
            var p = Math.min(100, Math.round(got / total * 100));
            if (bar) bar.value = p;
            if (label) label.textContent = "正在下載完整議題索引（" + p + "%）以重新計算…";
            return pump();
          });
        }
        return pump().then(function () {
          var buf = new Uint8Array(got);
          var off = 0;
          chunks.forEach(function (c) { buf.set(c, off); off += c.length; });
          return JSON.parse(new TextDecoder("utf-8").decode(buf));
        });
      }).then(function (payload) {
        indexPosts = (payload.posts || []).filter(function (p) { return cands[p.candidateId]; });
        setStatus("", false);
        return indexPosts;
      }).catch(function (err) {
        indexPromise = null;
        setStatus("無法取得議題索引，請稍後再試。", false);
        if (window.console) console.warn("spectrum: topic-index failed", err);
        throw err;
      });
      return indexPromise;
    }

    function recompute() {
      syncControls();
      var token = ++pending;
      loadIndex().then(function () {
        if (token !== pending) return;
        var out = compute();
        result = out.result;
        syncControls(out.intentCounts);
        render();
      }, function () {});
    }

    controls.addEventListener("click", function (ev) {
      var b = ev.target.closest("button");
      if (!b || !controls.contains(b)) return;
      if (b.hasAttribute("data-range")) {
        var r = +b.getAttribute("data-range");
        if (r === state.range) return;
        state.range = r;
        recompute();
      } else if (b.hasAttribute("data-topic")) {
        var t = b.getAttribute("data-topic");
        if (state.excluded[t]) delete state.excluded[t]; else state.excluded[t] = true;
        recompute();
      } else if (b.hasAttribute("data-intent")) {
        var k = b.getAttribute("data-intent");
        if (state.excludedIntents[k]) delete state.excludedIntents[k]; else state.excludedIntents[k] = true;
        recompute();
      } else if (b.hasAttribute("data-sort")) {
        var s = b.getAttribute("data-sort");
        if (s === state.sort) return;
        state.sort = s;
        syncControls();
        render();
      }
    });

    // Neutral default ordering: SSR is sorted by 最新更新; re-pick at random per load.
    syncControls();
    if (state.sort !== "latest") render();
  }

  /* ======================================================================
     /spectrum/<slug>/
     ====================================================================== */
  function initTopic() {
    var feed = doc.getElementById("topic-feed");
    if (!feed) return;
    var slug = feed.getAttribute("data-slug");
    var pages = +feed.getAttribute("data-pages") || 0;
    var shown = +feed.getAttribute("data-ssr") || 0;
    var STEP = 30;
    var moreWrap = MO.qs(".topic-river .feed-more");
    var moreBtn = doc.getElementById("topic-more");
    var statusEl = MO.qs(".topic-river-status");
    var countEl = MO.qs(".topic-river-count");
    var picker = MO.qs(".topic-picker");
    var chips = MO.qsa(".topic-pick", picker);
    var selected = {};
    var loaded = [];
    var nextPage = 1;
    var busy = false;
    var token = 0;

    function countFor(cid) {
      var chip = chips.filter(function (c) { return c.getAttribute("data-candidate") === cid; })[0];
      return chip ? +chip.getAttribute("data-count") || 0 : 0;
    }
    function selectedIds() { return Object.keys(selected); }
    function totalMatching() {
      var ids = selectedIds();
      if (!ids.length) return countFor("");
      return ids.reduce(function (s, id) { return s + countFor(id); }, 0);
    }
    function matches() {
      var ids = selectedIds();
      if (!ids.length) return loaded;
      return loaded.filter(function (p) { return selected[p.candidateId]; });
    }
    function setStatus(msg) {
      if (!statusEl) return;
      statusEl.textContent = msg || "";
      statusEl.hidden = !msg;
    }
    function fetchPage(n) {
      return MO.fetchJSON("/data/topic/" + slug + "/page-" + n + ".json").then(function (p) {
        if (n === nextPage) { loaded = loaded.concat(p.posts || []); nextPage += 1; }
      });
    }
    function ensure(n) {
      if (matches().length >= n || nextPage > pages) return Promise.resolve();
      return fetchPage(nextPage).then(function () { return ensure(n); });
    }
    function updateMore() {
      var total = totalMatching();
      if (moreWrap) moreWrap.hidden = shown >= total;
      if (countEl) countEl.textContent = "共 " + fmtN(total) + " 則・新到舊";
    }
    function append(list) {
      if (!list.length) return;
      var tmp = doc.createElement("div");
      tmp.innerHTML = list.map(function (p) { return MO.postHTML(p); }).join("");
      var nodes = Array.prototype.slice.call(tmp.children);
      nodes.forEach(function (n) { feed.appendChild(n); });
      MO.bindPostBehaviors(feed);
    }
    function withCandidates(fn) {
      return MO.loadCandidates().then(fn);
    }
    function loadMore() {
      if (busy) return;
      busy = true;
      var my = token;
      if (moreBtn) moreBtn.disabled = true;
      setStatus("正在取得更多貼文…");
      withCandidates(function () { return ensure(shown + STEP); }).then(function () {
        if (my !== token) return;
        var list = matches().slice(shown, shown + STEP);
        append(list);
        shown += list.length;
        setStatus("");
      }).catch(function () {
        setStatus("無法取得更多貼文，請稍後再試。");
      }).then(function () {
        busy = false;
        if (moreBtn) moreBtn.disabled = false;
        updateMore();
      });
    }
    function refilter() {
      token += 1;
      var my = token;
      busy = true;
      chips.forEach(function (c) {
        var cid = c.getAttribute("data-candidate");
        c.setAttribute("aria-pressed", String(cid ? !!selected[cid] : !selectedIds().length));
      });
      feed.innerHTML = "";
      shown = 0;
      setStatus("正在篩選貼文…");
      withCandidates(function () { return ensure(STEP); }).then(function () {
        if (my !== token) return;
        var list = matches().slice(0, STEP);
        append(list);
        shown = list.length;
        setStatus(list.length ? "" : "這些候選人目前沒有此議題的貼文。");
      }).catch(function () {
        if (my === token) setStatus("無法取得貼文，請稍後再試。");
      }).then(function () {
        if (my === token) busy = false;
        updateMore();
      });
    }

    if (moreBtn) moreBtn.addEventListener("click", loadMore);
    if (picker) picker.addEventListener("click", function (ev) {
      var b = ev.target.closest(".topic-pick");
      if (!b) return;
      var cid = b.getAttribute("data-candidate");
      if (!cid) selected = {};
      else if (selected[cid]) delete selected[cid];
      else selected[cid] = true;
      refilter();
    });
    updateMore();
  }

  function init() {
    if (doc.getElementById("spectrum-boot")) initIndex();
    if (doc.getElementById("topic-feed")) initTopic();
  }
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})();
