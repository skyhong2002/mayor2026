(() => {
  const stage = document.querySelector('#comparison-map-stage');
  if (!stage) return;
  const preview = stage.querySelector('#map-candidate-preview');
  const previewBody = stage.querySelector('.map-preview-body');
  const callouts = [...stage.querySelectorAll('.map-city-callout')];
  const regions = [...stage.querySelectorAll('.taiwan-map-region')];
  let active = null;
  let closeTimer = null;
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  const isMobile = () => window.matchMedia('(max-width: 699px)').matches;
  const candidatesFrom = (el) => {
    try { return JSON.parse(el.dataset.candidates || '[]'); }
    catch (_) { return []; }
  };
  const show = (el) => {
    if (!el || !previewBody) return;
    window.clearTimeout(closeTimer);
    active = el.dataset.city;
    callouts.forEach((item) => item.classList.toggle('is-active', item === el));
    const candidates = candidatesFrom(el);
    const name = el.querySelector('.map-city-name')?.textContent || '';
    const rows = candidates.map((candidate) => {
      const portrait = candidate.avatar
        ? `<img class="map-preview-avatar" src="${candidate.avatar}" alt="" width="34" height="34" loading="lazy">`
        : `<span class="map-preview-avatar" aria-hidden="true">${esc((candidate.name || '').slice(0, 1))}</span>`;
      const number = candidate.number == null ? '' : `號次 ${candidate.number} · `;
      const posts = candidate.postCount ? `${candidate.postCount.toLocaleString()} 則貼文` : '尚無收錄貼文';
      const safePortrait = candidate.avatar ? `<img class="map-preview-avatar" src="${esc(candidate.avatar)}" alt="" width="34" height="34" loading="lazy">` : portrait;
      return `<li class="map-preview-candidate">${safePortrait}<span><strong>${esc(candidate.name)}</strong><small>${esc(number)}${esc(candidate.party || '政黨資料待確認')} · ${esc(posts)}</small></span></li>`;
    }).join('');
    previewBody.innerHTML = `<p class="map-preview-kicker">候選人預覽</p><h3 class="map-preview-title">${esc(name)}</h3><ul class="map-preview-candidates">${rows}</ul><a class="map-preview-link" href="${esc(el.dataset.path)}">進入 ${esc(name)} 政見比較 <span aria-hidden="true">↗</span></a>`;
    preview.hidden = false;
  };
  const hide = () => {
    closeTimer = window.setTimeout(() => {
      preview.hidden = true;
      callouts.forEach((item) => item.classList.remove('is-active'));
      active = null;
    }, isMobile() ? 0 : 140);
  };
  const keepOpen = () => window.clearTimeout(closeTimer);

  callouts.forEach((el) => {
    el.addEventListener('mouseenter', () => { if (!isMobile()) show(el); });
    el.addEventListener('mouseleave', () => { if (!isMobile()) hide(); });
    el.addEventListener('focus', () => show(el));
    el.addEventListener('blur', () => { if (!isMobile()) hide(); });
    el.addEventListener('click', () => show(el));
  });
  regions.forEach((region) => {
    const slug = (region.getAttribute('href') || '').split('/').filter(Boolean).pop();
    const callout = callouts.find((el) => el.dataset.city === slug);
    if (!callout) return;
    region.addEventListener('mouseenter', () => { if (!isMobile()) show(callout); });
    region.addEventListener('mouseleave', () => { if (!isMobile()) hide(); });
    region.addEventListener('focus', () => show(callout));
    region.addEventListener('blur', () => { if (!isMobile()) hide(); });
    region.addEventListener('click', (event) => {
      if (isMobile()) {
        event.preventDefault();
        show(callout);
      }
    });
  });
  preview.addEventListener('mouseenter', keepOpen);
  preview.addEventListener('mouseleave', () => { if (!isMobile()) hide(); });
  preview.querySelector('.map-preview-close').addEventListener('click', () => {
    window.clearTimeout(closeTimer);
    preview.hidden = true;
    callouts.forEach((item) => item.classList.remove('is-active'));
    active = null;
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !preview.hidden) {
      preview.hidden = true;
      callouts.forEach((item) => item.classList.remove('is-active'));
      active = null;
    }
  });
})();
