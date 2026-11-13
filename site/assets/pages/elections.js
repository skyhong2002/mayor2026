/* /elections/: client-side candidate search over /data/elections/search-2026.json.
   Loaded lazily on first input (the index is ~1 MB, gzip ~250 KB). Pages work without JS. */
(function () {
  'use strict';
  var MO = window.MO;
  var form = document.querySelector('.el-search');
  if (!form || !MO) return;
  var input = form.querySelector('input');
  var out = document.querySelector('.el-results');
  var scope = form.getAttribute('data-scope') || '';
  var LIMIT = 80;
  var index = null;
  var loading = null;
  var timer = 0;

  function norm(s) { return String(s || '').replace(/[\s　]/g, '').replace(/台/g, '臺').toLowerCase(); }

  function load() {
    if (!loading) {
      loading = MO.fetchJSON('/data/elections/search-2026.json').then(function (d) {
        index = { data: d, rows: d.rows.map(function (r) {
          return { r: r, hay: norm(d.counties[r[3]] + r[4] + r[5] + r[0]) };
        }) };
        return index;
      });
    }
    return loading;
  }

  function scopeIdx(d) {
    if (!scope) return -1;
    var slugs = ['taipei', 'new-taipei', 'taoyuan', 'taichung', 'tainan', 'kaohsiung', 'yilan', 'hsinchu-county', 'miaoli',
      'changhua', 'nantou', 'yunlin', 'chiayi-county', 'pingtung', 'taitung', 'hualien', 'penghu', 'kinmen', 'lienchiang',
      'keelung', 'hsinchu-city', 'chiayi-city'];
    return slugs.indexOf(scope);
  }

  function render(q) {
    var d = index.data;
    var terms = q.split(/\s+/).map(norm).filter(Boolean);
    if (!terms.length) { out.hidden = true; out.innerHTML = ''; return; }
    var si = scopeIdx(d);
    var hits = [];
    var total = 0;
    for (var i = 0; i < index.rows.length; i++) {
      var row = index.rows[i];
      if (si >= 0 && row.r[3] !== si) continue;
      var ok = true;
      for (var t = 0; t < terms.length; t++) { if (row.hay.indexOf(terms[t]) < 0) { ok = false; break; } }
      if (!ok) continue;
      total++;
      if (hits.length < LIMIT) hits.push(row.r);
    }
    var html = '<p class="el-results-meta">' + (total ? '找到 ' + total.toLocaleString() + ' 位候選人' +
      (total > LIMIT ? '，顯示前 ' + LIMIT + ' 位；可加上縣市或鄉鎮縮小範圍' : '') : '找不到符合「' + MO.esc(q) + '」的候選人') + '</p>';
    html += hits.map(function (r) {
      var where = d.counties[r[3]] + (r[4] ? r[4] : '') + (r[5] && r[5] !== r[4] && r[5] !== d.counties[r[3]] ? r[5] : '');
      return '<a class="el-hit" href="' + MO.esc(r[6]) + '"><span class="ballot-no" aria-label="號次 ' + r[1] + '">' + r[1] + '</span>' +
        '<span><span class="el-hit-name">' + MO.esc(r[0]) + '</span> <span class="el-hit-where">' + MO.esc(where) + '・' + MO.esc(r[7]) +
        (r[8] ? '・2022 當選' : '') + '</span></span><span class="el-hit-cat">' + MO.esc(d.categories[r[2]]) + '</span></a>';
    }).join('');
    out.innerHTML = html;
    out.hidden = false;
  }

  function run() {
    var q = input.value.trim();
    if (!q) { out.hidden = true; out.innerHTML = ''; return; }
    load().then(function () { render(q); }).catch(function () {
      out.hidden = false;
      out.innerHTML = '<p class="el-results-meta">搜尋資料暫時無法取得，請稍後再試。</p>';
    });
  }

  input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 160); });
  input.addEventListener('focus', function () { load(); }, { once: true });
  form.addEventListener('submit', function (e) { e.preventDefault(); run(); });
  var params = new URLSearchParams(location.search);
  if (params.get('q')) { input.value = params.get('q'); run(); }
})();
