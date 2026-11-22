import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_issue_comparisons as B
from comparison_races import COUNTIES, race_roster, validate_race
from comparison_sources import PolicyPage, policy_url
from build_national_comparisons import recover_citations
from render import comparison, elections
from test_issue_comparisons import fixture
from test_comparison_facets import compact_fixture


def city_fixture(city='taoyuan'):
    data = fixture()
    name = next(name for slug, name, _ in COUNTIES if slug == city)
    data['race'] = {'id': city, 'name': name}
    data['candidates'] = race_roster(city)
    cid = data['candidates'][0]['id']
    for source in data['sources']:
        source['candidateId'] = cid
    data['claims'][0]['candidateId'] = cid
    next(t for t in data['topics'] if t['id'] == 'housing')['questions'][0]['rows'][0]['candidateId'] = cid
    return data


class NationalComparisonTests(unittest.TestCase):
    def test_rosters_cover_all_22_counties_and_81_registered_candidates(self):
        rosters = [race_roster(city) for city, _, _ in COUNTIES]
        self.assertEqual(len(rosters), 22)
        self.assertEqual(sum(map(len, rosters)), 81)
        self.assertEqual(len({c['id'] for rows in rosters for c in rows}), 81)

    def test_nantou_and_lienchiang_use_published_ballot_numbers(self):
        for city, names in (('nantou', ['許淑華', '温世政']), ('lienchiang', ['王忠銘', '曹爾元'])):
            with self.subTest(city=city):
                roster = race_roster(city)
                self.assertEqual([(c['number'], c['name']) for c in roster], list(enumerate(names, 1)))
                self.assertTrue(all(c['rosterSource'].startswith('https://web.cec.gov.tw/') for c in roster))

    def test_untracked_candidates_are_in_the_roster_with_stable_ids(self):
        first, second = race_roster('new-taipei'), race_roster('new-taipei')
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(len([c for c in first if not c['sourceTracked']]), 1)

    def test_missing_official_candidate_blocks_a_national_snapshot(self):
        data = city_fixture()
        B.validate_snapshot(data)
        data['candidates'].pop()
        with self.assertRaisesRegex(ValueError, 'complete official'):
            B.validate_snapshot(data)

    def test_cross_county_roster_and_fabricated_ballot_numbers_are_rejected(self):
        data = city_fixture('nantou')
        data['candidates'][0]['number'] = 999
        with self.assertRaisesRegex(ValueError, 'official roster'):
            validate_race(data)
        data = city_fixture()
        data['race'] = {'id': 'new-taipei', 'name': '新北市'}
        with self.assertRaisesRegex(ValueError, 'complete official'):
            validate_race(data)

    def test_city_render_has_its_own_route_api_and_all_official_candidates(self):
        data = city_fixture('nantou')
        data['sources'][1]['kind'] = 'policy'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'api').mkdir()
            (root / 'api/comparison.json').write_text('existing Taipei API')
            comparison.render_review(data, root, review=False, compact=compact_fixture(data))
            page = (root / 'compare/nantou/index.html').read_text()
            public = json.loads((root / 'api/comparisons/nantou.json').read_text())
            self.assertEqual((root / 'api/comparison.json').read_text(), 'existing Taipei API')
        self.assertIn('南投縣長選舉', page)
        self.assertIn('1 許淑華', page)
        self.assertIn('2 温世政', page)
        self.assertNotIn('>None<', page)
        self.assertIn('id="comparison-city"', page)
        self.assertIn('資料整理於', page)
        self.assertEqual(len(public['candidates']), 2)
        self.assertTrue(all('data-candidate-filter="' + c['id'] + '"' in page for c in data['candidates']))

    def test_hub_renders_in_place_and_copies_assets_to_a_separate_site(self):
        self.addCleanup(comparison.S.asset_hash.cache_clear)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            map_asset = root / 'scripts/assets/taiwan-map.svg'
            map_asset.parent.mkdir(parents=True)
            map_asset.write_text('<svg/>', encoding='utf-8')
            site = root / 'site'
            assets = {'comparison.css': '.comparison-hub {}', 'comparison-hub.js': '"use strict";'}
            (site / 'assets/pages').mkdir(parents=True)
            for name, content in assets.items():
                (site / 'assets/pages' / name).write_text(content, encoding='utf-8')

            with mock.patch.object(comparison.S, 'PROJECT_ROOT', root):
                for output in (site, root / 'preview'):
                    with self.subTest(output=output.name), mock.patch.object(comparison.S, 'ASSETS_DIR', output / 'assets'):
                        comparison.render_hub([], output)
                        self.assertTrue((output / 'compare/index.html').is_file())
                        for name, content in assets.items():
                            self.assertEqual((output / 'assets/pages' / name).read_text(encoding='utf-8'), content)

    def test_all_race_inputs_validate_before_any_production_page_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'data/comparisons'
            target.mkdir(parents=True)
            data = fixture()
            (target / 'taipei.json.gz').write_bytes(gzip.compress(json.dumps(data).encode()))
            (target / 'taipei-facets.json.gz').write_bytes(gzip.compress(json.dumps(compact_fixture(data)).encode()))
            with mock.patch.object(comparison.S, 'PROJECT_ROOT', root), mock.patch.object(comparison, 'render_review') as render:
                with self.assertRaises(FileNotFoundError):
                    comparison.render(None)
                render.assert_not_called()

    def test_policy_parser_keeps_all_heading_levels_and_collapsed_text(self):
        parser = PolicyPage()
        parser.feed('<html><head><title>Test</title></head><body><nav>導覽</nav><main><h1>福利</h1><details><summary>托育</summary><h3>資格</h3><p>設籍滿一年。</p><h6>補助上限</h6><p>三萬元。</p></details></main><script>secret()</script><footer>頁尾</footer></body></html>')
        self.assertEqual([h['level'] for h in parser.headings], ['h1', 'h3', 'h6'])
        self.assertIn('設籍滿一年。', parser.text())
        self.assertIn('三萬元。', parser.text())
        for hidden in ('導覽', 'secret()', '頁尾'):
            self.assertNotIn(hidden, parser.text())

    def test_policy_discovery_avoids_privacy_and_donation_pages(self):
        self.assertTrue(policy_url('https://example.test/politics/care/'))
        self.assertTrue(policy_url('https://example.test/policies/housing'))
        self.assertFalse(policy_url('https://example.test/privacy-policy'))
        self.assertFalse(policy_url('https://example.test/donate'))

    def test_mistyped_source_id_recovers_only_an_exact_quote_in_its_batch(self):
        data = fixture()
        rejected = {k: v for k, v in data['claims'][0].items() if k not in ('id', 'candidateId')}
        rejected['sourceId'] = 'mistyped-id'
        claims = []
        meta = [{'reviewed': ['s1'], 'rejected': [rejected]}]
        recovered = recover_citations(claims, meta, data['sources'])
        self.assertEqual(len(recovered), 1)
        self.assertEqual(claims[0]['sourceId'], 's1')
        self.assertEqual(claims[0]['candidateId'], 'c1')
        self.assertEqual(recover_citations(claims, meta, data['sources']), [])
        self.assertEqual(recover_citations([], [{'reviewed': [], 'rejected': [rejected]}], data['sources']), [])

    def test_shared_quote_does_not_guess_between_different_candidates(self):
        data = fixture()
        data['sources'][1]['candidateId'] = 'c2'
        rejected = {k: v for k, v in data['claims'][0].items() if k not in ('id', 'candidateId')}
        rejected['sourceId'] = 'mistyped-id'
        claims = []
        recovered = recover_citations(claims, [{'reviewed': ['s1', 's2'], 'rejected': [rejected]}], data['sources'])
        self.assertEqual(recovered, [])
        self.assertEqual(claims, [])

    def test_dense_policy_segments_complete_before_the_original_part_is_reviewed(self):
        data = fixture()
        source = {**data['sources'][0], 'text': ('資格與金額必須完整保留。\n' * 180)}
        calls = []
        def request(stage, prompt, payload, schema, maximum):
            calls.extend(s['id'] for s in payload)
            return {'inputHash': 'test', 'requestedModel': 'sky-quality', 'model': 'test-model',
                    'generatedAt': '2026-11-16', 'usage': {},
                    'result': {'reviewedSourceIds': [s['id'] for s in payload], 'claims': []}}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(B, 'WORK', Path(tmp)), mock.patch.object(B, 'request', side_effect=request):
            rows, meta = B.extraction_batch([source])
        self.assertEqual(rows, [])
        self.assertGreater(len(calls), 1)
        self.assertEqual(meta['reviewed'], ['s1'])
        self.assertEqual(len(meta['segments']), len(calls))
        data['sources'] = [source]
        data['claims'] = []
        for topic in data['topics']:
            topic['questions'] = []
        data['extractionProvenance'] = [meta]
        B.validate_snapshot(data)

    def test_election_pages_link_to_their_own_mayoral_race_only(self):
        self.assertIn('/compare/taoyuan/', elections._compare_link('taoyuan', 'municipal-mayor'))
        self.assertIn('/compare/yilan/', elections._compare_link('yilan', 'county-mayor'))
        self.assertEqual(elections._compare_link('yilan', 'county-councilor'), '')


if __name__ == '__main__':
    unittest.main()
