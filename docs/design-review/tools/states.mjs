// Screenshot inventory for the design review. docs/design-review/states.md
// documents the same IDs; change both together and only between rounds that
// re-shoot the baseline.
//
// site:   'full' (default, frozen data snapshot) | 'empty' (same build, zero posts)
// theme:  'light' (default) | 'dark'            (prefers-color-scheme)
// route:  [glob, 'hang' | 'error']               intercept a client JSON fetch
// click:  selectors clicked in order after load  anchor: start the shot at this element
// viewportOnly: one screen, no extension
export const SIZES = {
  desktop: { width: 2560, height: 1440, deviceScaleFactor: 1, maxHeight: 2160 },
  mobile: { width: 390, height: 844, deviceScaleFactor: 2, maxHeight: 1688, isMobile: true, hasTouch: true },
};

const CAND = '/taipei/shen-poyang/';
const SPARSE = '/kaohsiung/chang-ching/';
const PM = '/policy-match/#c=daily-transport,daily-housing,care-child';
const FEED = '**/data/feed/**';
const CANDPAGES = '**/data/candidate/**';
const INDEX = '**/data/search-index.json*';
const POLICY = '**/api/policy-match.json*';

export const STATES = [
  // 最新 /
  { id: 'home', path: '/' },
  { id: 'home-dark', path: '/', theme: 'dark' },
  { id: 'home-city', path: '/?city=taichung' },
  { id: 'home-filter-open', path: '/', click: ['.col-btn[data-act="filter"]:visible'], viewportOnly: true },
  { id: 'home-no-results', path: '/?q=zzqxv' },
  { id: 'home-loading', path: '/?city=taipei&topic=housing', route: [FEED, 'hang'] },
  { id: 'home-error', path: '/?city=taipei&topic=housing', route: [FEED, 'error'] },
  { id: 'home-empty', path: '/', site: 'empty' },
  { id: 'menu-open', path: '/', click: ['.nav-more > summary'], viewportOnly: true },
  // 候選人頁 /<city>/<id>/
  { id: 'cand', path: CAND },
  { id: 'cand-dark', path: CAND, theme: 'dark' },
  { id: 'cand-sparse', path: SPARSE },
  { id: 'cand-filter', path: CAND + '?topic=housing&platform=instagram', anchor: '#cand-feed-h' },
  { id: 'cand-no-results', path: CAND + '?q=zzqxv', anchor: '#cand-feed-h' },
  { id: 'cand-loading', path: CAND + '?q=%E6%8D%B7%E9%81%8B', route: [CANDPAGES, 'hang'], anchor: '#cand-feed-h' },
  { id: 'cand-error', path: CAND + '?q=%E6%8D%B7%E9%81%8B', route: [CANDPAGES, 'error'], anchor: '#cand-feed-h' },
  { id: 'cand-empty', path: CAND, site: 'empty' },
  // 候選人與來源 /source/
  { id: 'sources', path: '/source/' },
  { id: 'sources-filter', path: '/source/?city=kaohsiung' },
  { id: 'sources-no-results', path: '/source/?q=zzqxv' },
  { id: 'source-detail', path: '/source/shen-poyang/' },
  { id: 'source-detail-sparse', path: '/source/chang-ching/' },
  // 議題光譜
  { id: 'spectrum', path: '/spectrum/' },
  { id: 'spectrum-dark', path: '/spectrum/', theme: 'dark' },
  { id: 'spectrum-empty', path: '/spectrum/', site: 'empty' },
  { id: 'topic', path: '/spectrum/housing/' },
  { id: 'topic-empty', path: '/spectrum/housing/', site: 'empty' },
  // 議題選擇器
  { id: 'policy', path: '/policy-match/' },
  { id: 'policy-results', path: PM },
  { id: 'policy-results-dark', path: PM, theme: 'dark' },
  { id: 'policy-loading', path: PM, route: [POLICY, 'hang'] },
  { id: 'policy-error', path: PM, route: [POLICY, 'error'] },
  { id: 'policy-empty', path: PM, site: 'empty' },
  // 搜尋
  { id: 'search', path: '/search/' },
  { id: 'search-results', path: '/search/?q=%E6%8D%B7%E9%81%8B' },
  { id: 'search-filter', path: '/search/?q=%E6%8D%B7%E9%81%8B&city=taichung&platform=facebook' },
  { id: 'search-no-results', path: '/search/?q=zzqxv' },
  { id: 'search-loading', path: '/search/?q=%E6%8D%B7%E9%81%8B', route: [INDEX, 'hang'] },
  { id: 'search-error', path: '/search/?q=%E6%8D%B7%E9%81%8B', route: [INDEX, 'error'] },
  { id: 'search-empty', path: '/search/?q=%E6%8D%B7%E9%81%8B', site: 'empty' },
  // 其他
  { id: 'feeds', path: '/feeds/' },
  { id: 'status', path: '/status/' },
  { id: 'status-dark', path: '/status/', theme: 'dark' },
  { id: 'status-filter', path: '/status/?platform=instagram' },
  { id: 'status-empty', path: '/status/', site: 'empty' },
  { id: 'about', path: '/about/' },
  { id: 'not-found', path: '/no-such-page/' },
];

// Reference sites: photographed once (round 1) and reused in every round.
export const REFERENCES = [
  // READr：臺灣資料新聞與選舉專題（中文、資料視覺化）
  { id: 'readr-home', url: 'https://www.readr.tw/', locale: 'zh-TW' },
  { id: 'readr-election', url: 'https://www.readr.tw/category/election', locale: 'zh-TW' },
  // Ground News：跨來源新聞比較、立場分布
  { id: 'groundnews-home', url: 'https://ground.news/' },
  { id: 'groundnews-interest', url: 'https://ground.news/interest/taiwan' },
  // Bluesky：個人帳號貼文串
  { id: 'bluesky-profile', url: 'https://bsky.app/profile/bsky.app' },
  { id: 'bluesky-search', url: 'https://bsky.app/search?q=taipei' },
];

// Fixed clock: 28 minutes after the data snapshot (2026-11-11 06:02 GMT+8).
export const NOW = '2026-11-11T06:30:00+08:00';
