import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from comparison_facets import facet_id, snapshot_hash, validate_facets
from render import comparison
from test_issue_comparisons import fixture


def compact_fixture(data):
    return {'version': 1, 'snapshotHash': snapshot_hash(data), 'topics': [
        {'id': t['id'], 'name': t['name'], 'facets': [
            {'id': facet_id(t['id'], [q['id'] for q in t['questions']]), 'title': '社宅與居住支持',
             'questionIds': [q['id'] for q in t['questions']], 'rows': [
                {'candidateId': cid, 'verified': True,
                 'highlights': [{'text': next(r['summary'] for q in t['questions'] for r in q['rows'] if r['candidateId'] == cid),
                                 'claimIds': list(dict.fromkeys(ref for q in t['questions'] for r in q['rows'] if r['candidateId'] == cid for ref in r['claimIds']))}]} for cid in sorted({r['candidateId'] for q in t['questions'] for r in q['rows']})]}] if t['questions'] else []}
        for t in data['topics']]}


class FacetTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.compact = compact_fixture(self.data)
        self.facet = next(t for t in self.compact['topics'] if t['id'] == 'housing')['facets'][0]

    def test_complete_grouping(self):
        validate_facets(self.compact, self.data)

    def test_snapshot_change_is_rejected(self):
        self.data['claims'][0]['quote'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'source snapshot'):
            validate_facets(self.compact, self.data)

    def test_missing_question_is_rejected(self):
        self.facet['questionIds'] = []
        with self.assertRaises(ValueError):
            validate_facets(self.compact, self.data)

    def test_duplicate_question_is_rejected(self):
        self.facet['questionIds'] *= 2
        with self.assertRaises(ValueError):
            validate_facets(self.compact, self.data)

    def test_changed_question_set_requires_a_matching_anchor(self):
        self.facet['id'] = 'housing-overview-stale'
        with self.assertRaisesRegex(ValueError, 'ID does not match'):
            validate_facets(self.compact, self.data)

    def test_small_topic_has_at_most_two_facets(self):
        next(t for t in self.compact['topics'] if t['id'] == 'housing')['facets'] *= 3
        with self.assertRaisesRegex(ValueError, 'one to four'):
            validate_facets(self.compact, self.data)

    def test_cross_candidate_quote_is_rejected(self):
        self.facet['rows'][0]['candidateId'] = 'c2'
        with self.assertRaisesRegex(ValueError, 'every candidate'):
            validate_facets(self.compact, self.data)

    def test_unreviewed_summary_is_rejected(self):
        self.facet['rows'][0]['verified'] = False
        with self.assertRaisesRegex(ValueError, 'semantic verification'):
            validate_facets(self.compact, self.data)

    def test_unknown_or_unrelated_citation_is_rejected(self):
        self.facet['rows'][0]['highlights'][0]['claimIds'] = ['unknown']
        with self.assertRaisesRegex(ValueError, 'cite their candidate'):
            validate_facets(self.compact, self.data)

    def test_too_many_facets_are_rejected(self):
        next(t for t in self.compact['topics'] if t['id'] == 'housing')['facets'] *= 5
        with self.assertRaisesRegex(ValueError, 'one to four'):
            validate_facets(self.compact, self.data)

    def test_compact_table_keeps_original_evidence_and_has_no_auxiliary_sections(self):
        # A shared question needs one original anchor even when two candidates have quotes.
        self.data['sources'][1]['candidateId'] = 'c2'
        second = {**self.data['claims'][0], 'id': 'a2', 'candidateId': 'c2', 'sourceId': 's2'}
        self.data['claims'].append(second)
        q = next(t for t in self.data['topics'] if t['id'] == 'housing')['questions'][0]
        q['claimIds'].append('a2')
        q['rows'].append({'candidateId': 'c2', 'claimIds': ['a2'], 'summary': second['summary'], 'verified': True})
        compact = compact_fixture(self.data)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            comparison.render_review(self.data, root, compact=compact)
            html = (root / 'compare/taipei/index.html').read_text()
            api = json.loads((root / 'api/comparison.json').read_text())
        self.assertEqual(html.count('class="comparison-question comparison-facet"'), 1)
        self.assertEqual(html.count('id="housing-1"'), 1)
        for claim in self.data['claims']:
            self.assertIn('id="claim-' + claim['id'] + '"', html)
            self.assertIn(claim['quote'], html)
        for marker in ['政策原頁與全部小標', '完整來源庫', '資料資訊', '查看完整收錄文本', 'id="source-library"']:
            self.assertNotIn(marker, html)
        self.assertIn('細項與原文', html)
        self.assertIn('1 個比較項目', html)
        public_compact = api.pop('compactComparison')
        validate_facets(public_compact, api)
        self.assertEqual(len(api['claims']), len(self.data['claims']))

    def test_failed_compact_validation_does_not_replace_existing_page(self):
        self.compact['snapshotHash'] = 'stale'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / 'compare/taipei/index.html'
            existing.parent.mkdir(parents=True)
            existing.write_text('previous version')
            with self.assertRaises(ValueError):
                comparison.render_review(self.data, root, compact=self.compact)
            self.assertEqual(existing.read_text(), 'previous version')


if __name__ == '__main__':
    unittest.main()
