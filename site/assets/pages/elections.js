/* Candidate search: lazy global index, or immediate filtering of the current list. */
(function () {
  'use strict';
  var MO = window.MO, form = document.querySelector('.el-search');
  if (!form || !MO) return;
  var input = form.querySelector('input'), out = document.querySelector('.el-results');
  var status = document.querySelector('.el-search-status'), clear = form.querySelector('.el-clear');
  var county = form.querySelector('[name="county"]'), category = form.querySelector('[name="category"]');
  var local = form.dataset.local === 'true', scope = form.dataset.scope || '', catScope = form.dataset.category || '';
  var browse = document.querySelector('[data-el-browse]'), index, loading, timer, limit = 40, generation = 0, focusResult = -1;
  var slugs = ['taipei','new-taipei','taoyuan','taichung','tainan','kaohsiung','yilan','hsinchu-county','miaoli','changhua','nantou','yunlin','chiayi-county','pingtung','taitung','hualien','penghu','kinmen','lienchiang','keelung','hsinchu-city','chiayi-city'];
  var cats = ['municipal-mayor','county-mayor','municipal-councilor','county-councilor','township-mayor','indigenous-district-chief','township-rep','indigenous-district-rep','village-chief'];
  function norm(s) { return String(s || '').replace(/[\s　]/g, '').replace(/台/g, '臺').toLowerCase(); }
  function announce(s) { status.hidden = !s; status.textContent = s; }
  function active() { return input.value.trim() || (county && county.value) || (category && category.value); }
  function url() {
    var u = new URL(location.href);
    [['q', input.value.trim()], ['county', county && county.value], ['category', category && category.value]].forEach(function (p) {
      if (p[1]) u.searchParams.set(p[0], p[1]); else u.searchParams.delete(p[0]);
    });
    history.replaceState(null, '', u);
  }
  function load() {
    if (!loading) loading = MO.fetchJSON('/data/elections/search-2026.json').then(function (d) {
      index = { data: d, rows: d.rows.map(function (r) { return { r: r, hay: norm(d.counties[r[3]] + r[4] + r[5] + r[0] + r[7] + d.categories[r[2]]) }; }) };
      return index;
    }).catch(function (e) { loading = null; throw e; });
    return loading;
  }
  function localFilter(terms) {
    var visible = 0;
    document.querySelectorAll('.district').forEach(function (d) {
      var count = 0, heading = d.querySelector('.district-title').textContent;
      d.querySelectorAll('.ballot-item').forEach(function (row) {
        var hay = norm(heading + row.textContent);
        row.hidden = !terms.every(function (t) { return hay.includes(t); });
        if (!row.hidden) count++;
      });
      d.hidden = !count; visible += count;
    });
    announce(terms.length ? '找到 ' + visible.toLocaleString() + ' 位候選人' : '');
    out.hidden = visible !== 0;
    out.innerHTML = visible ? '' : '<div class="el-empty"><strong>查無符合的已收錄候選人</strong><p>試試姓名中的一個字、政黨或村里名稱。</p><button type="button" class="btn" data-reset>清除搜尋</button></div>';
  }
  function render(terms) {
    var d = index.data, si = slugs.indexOf(county ? county.value : scope), ci = cats.indexOf(category ? category.value : catScope);
    var hits = index.rows.filter(function (row) {
      return (si < 0 || row.r[3] === si) && (ci < 0 || row.r[2] === ci) && terms.every(function (t) { return row.hay.includes(t); });
    });
    announce('找到 ' + hits.length.toLocaleString() + ' 位候選人（已收錄）' + (hits.length > limit ? '，目前顯示 ' + limit + ' 位' : ''));
    out.innerHTML = hits.length ? '<div class="el-hit-list">' + hits.slice(0, limit).map(function (row) {
      var r = row.r, where = d.counties[r[3]] + (r[4] || '') + (r[5] && r[5] !== r[4] && r[5] !== d.counties[r[3]] ? r[5] : '');
      return '<a class="el-hit" href="' + MO.esc(r[6]) + '"><span class="ballot-no" aria-label="號次 ' + r[1] + '">' + r[1] + '</span><span class="el-hit-body"><span class="el-hit-name">' + MO.esc(r[0]) + '<span class="el-hit-party">' + MO.esc(r[7]) + '</span></span><span class="el-hit-where">' + MO.esc(where) + '</span></span><span class="el-hit-cat">' + MO.esc(d.categories[r[2]]) + '<span aria-hidden="true"> →</span></span></a>';
    }).join('') + '</div>' + (hits.length > limit ? '<button type="button" class="btn el-more" data-more>再顯示 40 位</button>' : '') : '<div class="el-empty"><strong>查無符合的已收錄候選人</strong><p>試試更短的姓名，或調整縣市與職位；部分號次公告仍在整理。</p><button type="button" class="btn" data-reset>清除搜尋與篩選</button></div>';
    out.hidden = false;
    if (focusResult >= 0) {
      var link = out.querySelectorAll('.el-hit')[focusResult]; focusResult = -1;
      if (link) link.focus();
    }
  }
  function run(write) {
    var token = ++generation, q = input.value.trim(), terms = q.split(/\s+/).map(norm).filter(Boolean);
    if (write !== false) url();
    clear.hidden = !active();
    if (local) { localFilter(terms); return; }
    if (browse) browse.hidden = !!active();
    if (!active()) { out.hidden = true; out.innerHTML = ''; announce(''); form.removeAttribute('aria-busy'); return; }
    announce('正在載入候選人名單…'); form.setAttribute('aria-busy', 'true');
    load().then(function () { if (token === generation) render(terms); }).catch(function () {
      if (token !== generation) return;
      announce('搜尋資料暫時無法載入');
      out.hidden = false;
      out.innerHTML = '<div class="el-empty"><p>請重試，或清除搜尋後依縣市瀏覽。</p><button type="button" class="btn" data-retry>重新載入</button> <button type="button" class="btn" data-reset>回到瀏覽</button></div>';
    }).finally(function () { if (token === generation) form.removeAttribute('aria-busy'); });
  }
  function reset() { input.value = ''; if (county) county.value = ''; if (category) category.value = ''; limit = 40; run(); input.focus(); }
  function restore() {
    var p = new URLSearchParams(location.search); input.value = p.get('q') || '';
    if (county) county.value = p.get('county') || ''; if (category) category.value = p.get('category') || '';
    run(false);
  }
  input.addEventListener('input', function () { clearTimeout(timer); limit = 40; generation++; timer = setTimeout(run, 120); });
  [county, category].filter(Boolean).forEach(function (select) { select.addEventListener('change', function () { limit = 40; run(); }); });
  form.addEventListener('submit', function (e) { e.preventDefault(); clearTimeout(timer); run(); });
  clear.addEventListener('click', reset);
  out.addEventListener('click', function (e) {
    if (e.target.closest('[data-reset]')) reset();
    if (e.target.closest('[data-retry]')) run();
    if (e.target.closest('[data-more]')) {
      focusResult = limit; limit += 40; run();
    }
  });
  var jump = document.getElementById('el-district');
  if (jump) jump.addEventListener('change', function () {
    if (!jump.value) return;
    if (input.value) { reset(); announce('已清除搜尋，跳到所選選區'); }
    var target = document.getElementById(jump.value);
    if (target) { location.hash = jump.value; target.setAttribute('tabindex', '-1'); target.focus({preventScroll:true}); target.scrollIntoView({block:'start'}); }
  });
  window.addEventListener('popstate', restore);
  restore();
})();
