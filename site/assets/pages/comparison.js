/* The complete comparison stays in the document; controls filter table rows and columns. */
(() => {
  'use strict';
  const app = document.querySelector('.comparison-app');
  if (!app) return;
  document.getElementById('comparison-city')?.addEventListener('change', event => {
    const destination = new URL(event.target.value, location.origin);
    const current = new URLSearchParams(location.search);
    for (const key of ['topics', 'topic', 'q', 'compare']) {
      if (current.has(key)) destination.searchParams.set(key, current.get(key));
    }
    location.assign(destination.href);
  });
  const input = document.getElementById('comparison-search');
  const topicFilters = Array.from(document.querySelectorAll('[data-topic-filter]'));
  const topicLabel = document.getElementById('selected-topic-label');
  const topicSelection = document.getElementById('topic-selection');
  const comparable = document.getElementById('only-comparable');
  const clearSearch = document.getElementById('clear-search');
  const scroller = document.querySelector('.comparison-table-scroll');
  const stickyHead = document.querySelector('.mobile-sticky-head');
  const stickyHeadInner = stickyHead?.querySelector('.mobile-sticky-head-inner');
  const tableHint = document.querySelector('.table-hint');
  const siteNav = document.querySelector('.site-nav');
  const stickyHeadHeight = () => stickyHead?.offsetHeight || (mobile.matches ? 58 : 0);
  const stickyContext = document.getElementById('mobile-sticky-context');
  const sections = Array.from(document.querySelectorAll('.comparison-topic'));
  const filters = Array.from(document.querySelectorAll('[data-candidate-filter]'));
  const columns = Array.from(document.querySelectorAll('[data-candidate]'));
  const mobile = window.matchMedia('(max-width: 699px)');
  const resetScroll = (fromInput = false) => {
    if (!mobile.matches) { scroller.scrollTop = 0; return; }
    if (fromInput) return;
    const top = scroller.getBoundingClientRect().top;
    const scrollY = Number.isFinite(window.scrollY) ? window.scrollY : 0;
    if (top < stickyHeadHeight() && typeof window.scrollTo === 'function') window.scrollTo({ top: Math.max(0, top + scrollY - stickyHeadHeight() - 8), behavior: 'smooth' });
  };
  const params = new URLSearchParams(location.search);
  const selected = params.get('candidates')?.split(',').filter(id => filters.some(f => f.dataset.candidateFilter === id));
  if (selected?.length) filters.forEach(f => { f.checked = selected.includes(f.dataset.candidateFilter); });
  const initialTopics = (params.get('topics') || params.get('topic') || '').split(',');
  topicFilters.forEach(f => { f.checked = initialTopics.includes(f.dataset.topicFilter); });
  comparable.checked = params.get('compare') === '1';
  input.value = params.get('q') || '';
  if (clearSearch) clearSearch.hidden = !input.value;

  function updateColumns() {
    const shown = new Set(filters.filter(f => f.checked).map(f => f.dataset.candidateFilter));
    columns.forEach(c => { c.hidden = !shown.has(c.dataset.candidate); });
    document.querySelectorAll('[data-table-span]').forEach(c => { c.colSpan = shown.size + (mobile.matches ? 0 : 1); });
    document.getElementById('selected-candidate-count').textContent = shown.size;
    scroller.style.setProperty('--candidate-count', shown.size);
    stickyHead?.style.setProperty('--candidate-count', shown.size);
    if (mobile.matches) {
      const candidateWidth = shown.size === 1 ? '100%' : 'calc((100vw - 32px)/2)';
      scroller.style.setProperty('--candidate-width', candidateWidth);
      stickyHead?.style.setProperty('--candidate-width', candidateWidth);
      scroller.scrollLeft = 0;
      if (stickyHeadInner) stickyHeadInner.style.transform = 'translateX(0)';
    } else {
      // The desktop table uses its fixed reading width. Dynamic mobile widths
      // must not leak into the desktop layout after a viewport resize.
      scroller.style.removeProperty('--candidate-width');
      stickyHead?.style.removeProperty('--candidate-width');
    }
  }

  function updateStickyContext() {
    if (!stickyContext || !mobile.matches) return;
    const head = stickyHead?.getBoundingClientRect();
    if (!head) return;
    const cutoff = head.top + stickyHead.offsetHeight + 8;
    const markers = [];
    sections.forEach(section => {
      if (section.hidden) return;
      const divider = section.querySelector('.topic-divider');
      if (divider && !divider.hidden) markers.push({ node: divider, text: section.dataset.topicName || '' });
      section.querySelectorAll('.mobile-question-heading').forEach(heading => {
        if (heading.hidden) return;
        const link = heading.querySelector('a');
        if (link) markers.push({ node: heading, text: `${section.dataset.topicName || ''} · ${link.textContent.trim()}` });
      });
    });
    let current = markers[0];
    markers.forEach(marker => {
      if (marker.node.getBoundingClientRect().top <= cutoff) current = marker;
    });
    if (current?.text) stickyContext.textContent = `正在閱讀：${current.text}`;
  }

  function openForSearch(detail) {
    if (detail && !detail.open) { detail.open = true; detail.dataset.searchOpened = 'true'; }
  }
  function restoreSearchOpen(detail) {
    if (detail?.dataset.searchOpened) { detail.open = false; delete detail.dataset.searchOpened; }
  }

  function update(writeURL = true) {
    const query = input.value.trim().toLocaleLowerCase();
    const chosenTopics = topicFilters.filter(f => f.checked).map(f => f.dataset.topicFilter);
    const allTopics = !chosenTopics.length || chosenTopics.length === topicFilters.length;
    topicLabel.textContent = allTopics ? '所有議題' : (chosenTopics.length === 1 ? topicFilters.find(f => f.checked).nextElementSibling.textContent : `已選 ${chosenTopics.length} 個議題`);
    topicSelection.replaceChildren();
    topicSelection.hidden = allTopics;
    if (!allTopics) topicFilters.filter(f => f.checked).forEach(f => {
      const chip = document.createElement('button'); chip.type = 'button';
      chip.textContent = f.nextElementSibling.textContent + ' ×';
      chip.setAttribute('aria-label', '移除議題：' + f.nextElementSibling.textContent);
      chip.addEventListener('click', () => { f.checked = false; update(); });
      topicSelection.append(chip);
    });
    const shownCandidates = new Set(filters.filter(f => f.checked).map(f => f.dataset.candidateFilter));
    let count = 0;
    sections.forEach(section => {
      const matchesTopic = allTopics || chosenTopics.includes(section.dataset.topic);
      const questions = Array.from(section.querySelectorAll('.comparison-question'));
      let matches = 0;
      questions.forEach(q => {
        const candidateCount = q.dataset.claimCandidates ? q.dataset.claimCandidates.split(',').filter(id => shownCandidates.has(id)).length : 0;
        q.hidden = (!!query && !q.dataset.search.includes(query)) || (comparable.checked && candidateCount < 2);
        const titleMatches = !query || q.querySelector('.question-label a').textContent.toLocaleLowerCase().includes(query);
        q.querySelectorAll('.facet-detail').forEach(detail => {
          detail.hidden = !!query && !titleMatches && !detail.dataset.detailSearch.includes(query);
          const quotes = detail.querySelector('.detail-quotes');
          if (query && !detail.hidden && detail.querySelector('blockquote') && Array.from(detail.querySelectorAll('blockquote')).some(b => b.textContent.toLocaleLowerCase().includes(query))) {
            openForSearch(quotes);
          } else restoreSearchOpen(quotes);
        });
        const detailList = q.querySelectorAll('.facet-evidence');
        detailList.forEach(list => {
          if (query && Array.from(list.querySelectorAll('.facet-detail')).some(d => !d.hidden)) openForSearch(list);
          else restoreSearchOpen(list);
        });
        q.previousElementSibling.hidden = q.hidden;
        if (!q.hidden) matches++;
      });
      section.hidden = !matchesTopic || !matches;
      if (!section.hidden) count += matches;
    });
    document.getElementById('result-count').textContent = `${count} 個比較項目`;
    document.getElementById('comparison-no-results').hidden = count !== 0;
    if (clearSearch) clearSearch.hidden = !input.value.trim();
    if (writeURL) {
      const url = new URL(location.href);
      url.searchParams.delete('topic');
      allTopics ? url.searchParams.delete('topics') : url.searchParams.set('topics', chosenTopics.join(','));
      query ? url.searchParams.set('q', input.value.trim()) : url.searchParams.delete('q');
      comparable.checked ? url.searchParams.set('compare', '1') : url.searchParams.delete('compare');
      const selected = filters.filter(f => f.checked).map(f => f.dataset.candidateFilter);
      selected.length === filters.length ? url.searchParams.delete('candidates') : url.searchParams.set('candidates', selected.join(','));
      history.replaceState(null, '', url);
    }
  }
  topicFilters.forEach(f => f.addEventListener('change', () => { update(); resetScroll(); }));
  document.getElementById('all-topics').addEventListener('click', () => { topicFilters.forEach(f => { f.checked = false; }); update(); resetScroll(); });
  document.getElementById('reset-comparison').addEventListener('click', () => { topicFilters.forEach(f => { f.checked = false; }); input.value = ''; comparable.checked = false; update(); resetScroll(); });
  input.addEventListener('input', () => { update(); resetScroll(true); });
  comparable.addEventListener('change', () => { update(); resetScroll(); });
  clearSearch?.addEventListener('click', () => { input.value = ''; update(); input.focus(); });
  filters.forEach(filter => filter.addEventListener('change', () => {
    if (!filters.some(f => f.checked)) filter.checked = true;
    updateColumns();
    update();
    if (mobile.matches) resetScroll();
  }));
  mobile.addEventListener('change', () => { updateColumns(); if (stickyHeadInner && !mobile.matches) stickyHeadInner.style.transform = ''; });
  scroller.addEventListener('scroll', () => {
    if (stickyHeadInner && mobile.matches) stickyHeadInner.style.transform = `translateX(${-scroller.scrollLeft}px)`;
    if (tableHint && mobile.matches && scroller.scrollLeft > 8) tableHint.hidden = true;
  }, { passive: true });
  const menus = Array.from(document.querySelectorAll('.candidate-menu'));
  document.addEventListener('click', event => { menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }); });
  menus.forEach(menu => {
    menu.addEventListener('toggle', () => { if (menu.open) menus.forEach(other => { if (other !== menu) other.open = false; }); });
    menu.addEventListener('keydown', event => { if (event.key === 'Escape') { menu.open = false; menu.querySelector('summary').focus(); } });
  });

  function revealHash(preserveFilters = false) {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id) || (id.startsWith('source-') ? document.querySelector('[data-source-id="' + CSS.escape(id.slice(7)) + '"]') : null);
    if (!target) return;
    const topic = target.closest('.comparison-topic');
    const hasUrlFilters = ['topics', 'topic', 'q', 'compare', 'candidates'].some(key => new URLSearchParams(location.search).has(key));
    if (topic && !preserveFilters && !hasUrlFilters) {
      topicFilters.forEach(f => { f.checked = f.dataset.topicFilter === topic.dataset.topic; });
      input.value = '';
      comparable.checked = false;
      const cell = target.closest('[data-candidate]');
      if (cell) {
        const filter = filters.find(f => f.dataset.candidateFilter === cell.dataset.candidate);
        if (filter) filter.checked = true;
        updateColumns();
      }
      update();
    }
    for (let element = target; element; element = element.parentElement) {
      if (element.tagName === 'DETAILS') element.open = true;
    }
    requestAnimationFrame(() => {
      if (topic) {
        scroller.scrollIntoView({ block: 'start' });
        const row = target.closest('.comparison-question');
        const scrollTarget = mobile.matches && target === row ? row.previousElementSibling : target;
        const bounds = scrollTarget.getBoundingClientRect();
        const viewport = scroller.getBoundingClientRect();
        const headerHeight = mobile.matches ? stickyHeadHeight() : scroller.querySelector('thead').getBoundingClientRect().height;
        if (mobile.matches && typeof window.scrollBy === 'function') window.scrollBy({ top: bounds.top - headerHeight - 12, behavior: 'auto' });
        else scroller.scrollTop += bounds.top - viewport.top - headerHeight - 12;
        const cell = target.closest('td');
        if (cell) {
          const labelWidth = scroller.querySelector('.corner-cell').getBoundingClientRect().width;
          scroller.scrollLeft += cell.getBoundingClientRect().left - viewport.left - labelWidth;
        }
      } else target.scrollIntoView({ block: 'start' });
    });
  }
  document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', event => {
    const inComparisonRow = a.closest('.comparison-question,.mobile-question-heading');
    if (inComparisonRow) {
      event.preventDefault();
      history.replaceState(null, '', a.getAttribute('href'));
      requestAnimationFrame(() => revealHash(true));
    } else requestAnimationFrame(() => revealHash());
  }));
  window.addEventListener('hashchange', revealHash);
  updateColumns();
  update(false);
  if (location.hash) revealHash();

  // Keep the current issue visible while a long policy row is being read.
  updateStickyContext();
  window.addEventListener('scroll', () => requestAnimationFrame(updateStickyContext), { passive: true });
  scroller.addEventListener('scroll', () => requestAnimationFrame(updateStickyContext), { passive: true });

  // On a phone, open the dense facet evidence in a full-width reading layer.
  // The original details element is restored in place when the reader closes it.
  let activeEvidence = null;
  let evidencePlaceholder = null;
  let readingLayer = null;
  let previousBodyOverflow = '';
  const closeEvidence = () => {
    if (!activeEvidence) return;
    activeEvidence.open = false;
    if (evidencePlaceholder?.parentNode) evidencePlaceholder.parentNode.insertBefore(activeEvidence, evidencePlaceholder.nextSibling);
    evidencePlaceholder?.remove();
    activeEvidence.classList.remove('mobile-reading-portal');
    activeEvidence = null;
    evidencePlaceholder = null;
    if (readingLayer) readingLayer.hidden = true;
    document.body.style.overflow = previousBodyOverflow;
    document.body.classList.remove('mobile-evidence-open');
  };
  const openEvidence = detail => {
    if (!mobile.matches || !detail || activeEvidence === detail) return;
    closeEvidence();
    readingLayer ||= (() => {
      const layer = document.createElement('div');
      layer.className = 'mobile-reading-layer';
      layer.hidden = true;
      layer.innerHTML = '<div class="mobile-reading-toolbar"><strong>細項與原文</strong><button type="button" class="text-button mobile-reading-close">完成</button></div><div class="mobile-reading-content"></div>';
      layer.querySelector('.mobile-reading-close').addEventListener('click', closeEvidence);
      document.body.append(layer);
      return layer;
    })();
    evidencePlaceholder = document.createComment('facet evidence position');
    detail.parentNode.insertBefore(evidencePlaceholder, detail);
    readingLayer.querySelector('.mobile-reading-content').append(detail);
    detail.classList.add('mobile-reading-portal');
    detail.open = true;
    activeEvidence = detail;
    previousBodyOverflow = document.body.style.overflow;
    readingLayer.hidden = false;
    document.body.style.overflow = 'hidden';
    document.body.classList.add('mobile-evidence-open');
  };
  document.querySelectorAll('.facet-evidence').forEach(detail => {
    detail.addEventListener('click', event => {
      const summary = event.target.closest('summary');
      if (summary?.parentElement === detail) detail.dataset.userToggle = 'true';
    }, true);
    detail.addEventListener('toggle', () => {
      const userToggle = detail.dataset.userToggle === 'true';
      delete detail.dataset.userToggle;
      if (!userToggle || !mobile.matches) return;
      if (detail.open) openEvidence(detail);
      else if (activeEvidence === detail) closeEvidence();
    });
  });
  window.addEventListener('keydown', event => { if (event.key === 'Escape') closeEvidence(); });

  // On the comparison page, hide the global bottom navigation while reading
  // downward so the policy table is the only persistent focus. It returns as
  // soon as the reader scrolls up or reaches the top.
  if (document.body.classList.contains('comparison-detail')) {
    let lastScrollY = window.scrollY;
    let direction = 0;
    let distance = 0;
    let scrollTick = false;
    const syncReadingChrome = () => {
      const current = window.scrollY;
      const delta = current - lastScrollY;
      const nextDirection = delta > 0 ? 1 : delta < 0 ? -1 : direction;
      if (nextDirection !== direction) distance = 0;
      direction = nextDirection;
      distance += Math.abs(delta);
      if (current <= 12 || (direction < 0 && distance >= 32)) {
        document.body.classList.remove('comparison-reading');
        if (siteNav) siteNav.inert = false;
      } else if (direction > 0 && distance >= 24) {
        document.body.classList.add('comparison-reading');
        if (siteNav) siteNav.inert = true;
      }
      lastScrollY = current;
      scrollTick = false;
    };
    window.addEventListener('scroll', () => {
      if (!scrollTick) { scrollTick = true; requestAnimationFrame(syncReadingChrome); }
    }, { passive: true });
  }
})();
