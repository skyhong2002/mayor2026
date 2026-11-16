"""Read-only policy source snapshots from verified campaign websites."""
from __future__ import annotations
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import build_issue_comparisons as B


class PolicyPage(HTMLParser):
    """Keep full visible text and every heading, including collapsed policy sections."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'wbr'}
    SKIP = {'script', 'style', 'nav', 'header', 'footer', 'noscript', 'form', 'svg'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts, self.headings, self.links = [], [], []
        self.heading, self.heading_parts, self.title = '', [], ''
        self.date = ''

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and a.get('href'):
            self.links.append(a['href'])
        if tag == 'meta' and (a.get('property') or a.get('name')) in ('article:published_time', 'datePublished'):
            self.date = a.get('content') or ''
        if tag not in self.VOID:
            self.stack.append(tag)
        if any(t in self.SKIP for t in self.stack):
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.heading, self.heading_parts = tag, []
        if tag in ('p', 'li', 'div', 'section', 'article', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == self.heading:
            text = ''.join(self.heading_parts).strip()
            if text:
                self.headings.append({'level': tag, 'text': text})
            self.heading = ''
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]
        if tag in ('p', 'li', 'div', 'section', 'article'):
            self.parts.append('\n')

    def handle_data(self, text):
        if 'title' in self.stack:
            self.title += text
        if any(t in self.SKIP for t in self.stack) or 'head' in self.stack:
            return
        self.parts.append(text)
        if self.heading:
            self.heading_parts.append(text)

    def text(self):
        return '\n'.join(s.strip() for s in ''.join(self.parts).splitlines() if s.strip())


def policy_url(url: str) -> bool:
    path = urllib.parse.unquote(urllib.parse.urlsplit(url).path).lower()
    return bool(re.search(r'/(?:polic(?:y|ies)|politics|future|vision|towns)(?:/|$)|政見|政策', path))


def crawl_campaign(account: dict, cache: Path) -> tuple[list[dict], list[dict]]:
    root = account['url']
    host = urllib.parse.urlsplit(root).hostname
    pending, seen, docs, failures = [root], set(), [], []
    while pending:
        url = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        path = cache / (B.digest(url) + '.html')
        try:
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(B.fetch(url))
            page = PolicyPage()
            page.feed(path.read_text(errors='replace'))
            text = page.text()
            today = B.dt.datetime.now(B.dt.timezone(B.dt.timedelta(hours=8))).date().isoformat()
            in_window = not page.date or '2026-01-01' <= page.date[:10] <= today
            if len(text) >= 80 and in_window:
                sid = B.digest([url, text])[:20]
                docs.append({'id': sid, 'candidateId': account['candidate_id'], 'url': url, 'text': text,
                             'postedAt': page.date, 'fetchedAt': B.dt.datetime.fromtimestamp(path.stat().st_mtime, B.dt.timezone.utc).isoformat(), 'platform': 'website', 'kind': 'policy',
                             'headings': page.headings, 'title': next((h['text'] for h in page.headings if h['level']=='h1'), page.title.strip()),
                             'verification': account['verification'], 'accountRole': account['account_role']})
            for href in page.links:
                link = urllib.parse.urljoin(url, href)
                p = urllib.parse.urlsplit(link)
                link = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, '', ''))
                article = account.get('policyArticlePattern')
                is_policy = policy_url(link) or bool(article and (url == root or policy_url(url)) and re.search(article, p.path))
                if p.scheme in ('http', 'https') and p.hostname == host and is_policy and link not in seen and link not in pending:
                    pending.append(link)
        except Exception as exc:
            failures.append({'url': url, 'error': str(exc)[:200]})
    return docs, failures


def merge_supplement(manifest: dict, supplement: dict) -> dict:
    """Append newly discovered policy documents without reshuffling extraction batches."""
    if supplement['failures']:
        raise ValueError('Discovered policy pages could not be read')
    known = {s['clusterId']: s for s in manifest['sources']}
    for doc in supplement['sources']:
        cluster = B.digest([doc['candidateId'], B.normalize(doc['text'])])[:20]
        variant = {k: doc[k] for k in ('url', 'platform', 'postedAt')}
        if cluster in known:
            if variant not in known[cluster]['alternatives']:
                known[cluster]['alternatives'].append(variant)
            continue
        if doc['candidateId'] not in {c['id'] for c in manifest['candidates']}:
            raise ValueError('Supplement belongs to another race')
        row = {**doc, 'clusterId': cluster, 'alternatives': [variant]}
        manifest['sources'].append(row)
        known[cluster] = row
        manifest['rawSourceCount'] += 1
    return manifest


def prepare_manifests(inbox: Path, published: Path, work: Path):
    from comparison_races import COUNTIES, race_roster
    import feed_common
    accounts = {a['account_id']: a for a in feed_common.load_accounts()}
    configuration = json.loads((B.ROOT / 'data/comparisons/website-sources.json').read_text())
    extra = configuration['sources']
    for a in extra:
        if a['verification'] not in ('first_party', 'cross_ref') or not a.get('evidenceUrl'):
            raise ValueError('Supplementary campaign sources require recorded identity evidence')
        accounts[a['account_id']] = a
    for account in accounts.values():
        account.update(configuration.get('discovery', {}).get(account['candidate_id'], {}))
    rosters = {city: race_roster(city) for city, _, _ in COUNTIES if city != 'taipei'}
    candidate_cities = {c['id']: city for city, rows in rosters.items() for c in rows}
    by_city = {city: {} for city in rosters}
    rejected = {city: {'outsideWindow': 0, 'unverifiedSource': 0, 'noText': 0} for city in rosters}
    today = B.dt.datetime.now(B.dt.timezone(B.dt.timedelta(hours=8))).date().isoformat()
    for line in inbox.open():
        row = json.loads(line)
        cid = row.get('candidate_id')
        city = candidate_cities.get(cid)
        if not city:
            continue
        a = accounts.get(row.get('source_id'))
        if not a or a['candidate_id'] != cid or a['city'] != city or a.get('verification') not in ('first_party', 'cross_ref'):
            rejected[city]['unverifiedSource'] += 1
            continue
        text, date = (row.get('text') or '').strip(), row.get('posted_at') or ''
        if date and not '2026-01-01' <= date[:10] <= today:
            rejected[city]['outsideWindow'] += 1
            continue
        if not text:
            rejected[city]['noText'] += 1
            continue
        sid = B.digest([cid, row.get('url'), text])[:20]
        by_city[city][sid] = {'id': sid, 'candidateId': cid, 'text': text, 'url': row.get('url') or '',
                              'postedAt': date, 'fetchedAt': row.get('fetched_at') or '', 'platform': row['platform'],
                              'kind': 'post', 'headings': [], 'title': text.splitlines()[0][:80],
                              'verification': a['verification'], 'accountRole': a['account_role']}
    web_failures = {city: [] for city in rosters}
    for a in accounts.values():
        city = candidate_cities.get(a['candidate_id'])
        if city and a['platform'] == 'website' and a['account_role'] == 'campaign' and a['verification'] in ('first_party', 'cross_ref'):
            docs, failures = crawl_campaign(a, work / 'web-pages')
            by_city[city].update({d['id']: d for d in docs})
            web_failures[city].extend(failures)
            print('campaign sources', city, a['candidate_id'], len(docs), 'failures', len(failures), flush=True)
    profiles = json.loads((published / 'api/candidates.json').read_text())['candidates']
    for city, name, _ in COUNTIES:
        if city == 'taipei':
            continue
        docs = list(by_city[city].values())
        clusters = {}
        for doc in docs:
            clusters.setdefault(B.digest([doc['candidateId'], B.normalize(doc['text'])]), []).append(doc)
        sources = []
        for key, variants in clusters.items():
            first = sorted(variants, key=lambda d: (d['kind'] != 'policy', d['platform'] != 'website', d['id']))[0]
            sources.append({**first, 'clusterId': key[:20], 'alternatives': [
                {k: d[k] for k in ('url', 'platform', 'postedAt')} for d in variants]})
        manifest = {'version': 'national-comparison-v1', 'race': {'id': city, 'name': name},
                    'generatedAt': B.NOW(), 'windowStart': '2026-01-01', 'candidates': rosters[city],
                    'sources': sorted(sources, key=lambda s: s['id']), 'rawSourceCount': len(docs),
                    'policyFailures': [], 'sourceFailures': web_failures[city], 'excluded': rejected[city],
                    'limitations': ['貼文僅代表已收錄範圍；圖片、影片語音與未取得的選舉公報尚未納入。',
                                    '完整名單依官方登記與號次公告；號次未取得時標示待公告。',
                                    '官網政見為已確認競選網站的可取得文字；無日期時保留日期不詳。']}
        path = work / city / 'manifest.json'
        if path.exists():
            old = json.loads(path.read_text())
            # Preserve the snapshot timestamp so resumptions keep extraction cache keys stable.
            if B.digest(old['sources']) == B.digest(manifest['sources']):
                manifest['generatedAt'] = old['generatedAt']
        B.save(path, manifest)
        for c in rosters[city]:
            profile = next((p for p in profiles if p['id'] == c['id']), {})
            avatar = profile.get('avatarUrl') or ''
            if avatar.startswith('assets/source-avatars/') and (published / avatar).is_file():
                import shutil
                dest = Path('site/assets/comparison-avatars') / (c['id'] + '.webp')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(published / avatar, dest)
        print('prepared', city, len(rosters[city]), 'candidates', len(sources), 'texts', sum(len(s['text']) for s in sources), 'chars', flush=True)
