import datetime as dt
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import instagram_public_fetcher as ig
import apify_facebook_fetcher as fb
import run_pipeline

SOURCE = {'id': 'ig-test', 'platform': 'instagram', 'username': 'test',
          'candidate_id': 'candidate', 'city': 'taipei'}
NOW = dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc)
PROFILE = {'username': 'test', 'latestPosts': [{'id': '1', 'shortCode': 'abc',
    'timestamp': '2026-10-15T12:00:00Z', 'caption': 'hello', 'displayUrl': 'https://cdn/image'}]}


class InstagramTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        for obj, attr, name in ((ig.feed_common, 'ERRORS_JSONL', 'errors.jsonl'),
                                 (fb, 'LEDGER_JSON', 'ledger.json'),
                                 (ig.source_status, 'STATE_PATH', 'status.json'),
                                 (ig.ig_public_host, 'STATE_PATH', 'host.json')):
            patch = mock.patch.object(obj, attr, Path(self.directory.name) / name)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.dict('os.environ', {'APIFY_TOKEN': 'test-token',
            'MAYOR_APIFY_INSTAGRAM_MONTHLY_BUDGET_USD': '.75'})
        patch.start()
        self.addCleanup(patch.stop)

    def response(self, data):
        return io.BytesIO(json.dumps(data).encode())

    def test_direct_http_success_shape(self):
        client = ig.PublicInstagramClient()
        client.lsd = 'anonymous'
        payload = {'data': {'xdt_api__v1__feed__user_timeline_graphql_connection': {
            'edges': [{'node': {'pk': '1', 'code': 'abc', 'taken_at': 1792065600,
                'caption': {'text': 'hello'}, 'image_versions2': {'candidates': [{'url': 'https://cdn/image'}]}}}]}}}
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = 'https://www.instagram.com/graphql/query'
        response.read.return_value = json.dumps(payload).encode()
        with mock.patch.object(client.opener, 'open', return_value=response):
            rows = client.fetch(SOURCE)[1]
        self.assertEqual(set(rows[0]), {'id', 'candidate_id', 'city', 'platform', 'source_id',
                                      'url', 'posted_at', 'text', 'media', 'fetched_at'})
        self.assertEqual(rows[0]['id'], 'instagram:https://www.instagram.com/p/abc/')
        self.assertTrue(rows[0]['posted_at'].endswith('+00:00'))
        self.assertEqual(rows[0]['media'], ['https://cdn/image'])

    def test_refusal_blocks_host_and_falls_back(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 5}, 'current': {'monthlyUsageUsd': 1}}}
        run = {'data': {'id': 'run', 'status': 'SUCCEEDED', 'defaultDatasetId': 'dataset', 'usageTotalUsd': .008}}
        with mock.patch.object(ig.feed_common, 'load_sources', return_value=[SOURCE]), \
             mock.patch.object(ig, 'fetch_public_profile', side_effect=ig.PublicWebError('HTTP 401', 401)), \
             mock.patch.object(ig.urllib.request, 'urlopen', side_effect=[self.response(limits), self.response(run), self.response([PROFILE])]) as http, \
             mock.patch.object(ig.feed_common, 'append_jsonl_dedup', return_value=1) as append, \
             mock.patch.object(sys, 'argv', ['instagram_public_fetcher.py']):
            self.assertEqual(ig.main(), 0)
        self.assertEqual(json.loads(ig.ig_public_host.STATE_PATH.read_text())['blockedBy'], 'mayor2026')
        self.assertEqual(append.call_args.args[1][0]['id'], 'instagram:https://www.instagram.com/p/abc/')
        self.assertEqual(http.call_count, 3)
        ledger = json.loads(fb.LEDGER_JSON.read_text())
        self.assertEqual(ledger['months'][NOW.strftime('%Y-%m')]['instagram']['estimated_spend_usd'], .008)

    def test_existing_host_block_falls_back_without_extending_it(self):
        until = ig.ig_public_host.report_block('chumei', seconds=600)
        with mock.patch.object(ig.feed_common, 'load_sources', return_value=[SOURCE]), \
             mock.patch.object(ig, 'fetch_public_profile') as direct, \
             mock.patch.object(ig, 'apify_profiles', return_value={'test': PROFILE}), \
             mock.patch.object(ig.feed_common, 'append_jsonl_dedup', return_value=1) as append, \
             mock.patch.object(sys, 'argv', ['instagram_public_fetcher.py']):
            self.assertEqual(ig.main(), 0)
        direct.assert_not_called()
        host = json.loads(ig.ig_public_host.STATE_PATH.read_text())
        self.assertEqual((host['blockedBy'], host['blockedUntil']), ('chumei', until))
        self.assertEqual(append.call_args.args[1][0]['source_id'], 'ig-test')

    def test_repeated_query_failures_stop_direct_attempts(self):
        sources = [{**SOURCE, 'id': f'ig-{n}', 'username': f'user{n}'} for n in range(5)]
        with mock.patch.object(ig.feed_common, 'load_sources', return_value=sources), \
             mock.patch.object(ig.ig_public_host, 'wait_turn', return_value=True), \
             mock.patch.object(ig, 'fetch_public_profile', side_effect=ValueError('no timeline')) as direct, \
             mock.patch.object(ig, 'apify_profiles', side_effect=RuntimeError('Apify skipped')), \
             mock.patch.object(sys, 'argv', ['instagram_public_fetcher.py']):
            self.assertEqual(ig.main(), 0)
        self.assertEqual(direct.call_count, ig.DIRECT_MAX_CONSECUTIVE_FAILURES)
        self.assertFalse(ig.ig_public_host.STATE_PATH.exists() and
                         json.loads(ig.ig_public_host.STATE_PATH.read_text()).get('blockedBy'))

    def test_monthly_cap_skips_http(self):
        ig.feed_common.save_json_atomic(fb.LEDGER_JSON, {'months': {'2026-10': {
            'instagram': {'estimated_spend_usd': .748, 'runs': 1}}}})
        with mock.patch.object(ig.urllib.request, 'urlopen') as http:
            with self.assertRaisesRegex(RuntimeError, 'monthly budget'):
                ig.apify_profiles([SOURCE], now=NOW)
        http.assert_not_called()

    def test_live_limit_skips_paid_post(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 5}, 'current': {'monthlyUsageUsd': 4.75}}}
        with mock.patch.object(ig.urllib.request, 'urlopen', return_value=self.response(limits)) as http:
            with self.assertRaisesRegex(RuntimeError, 'live credit'):
                ig.apify_profiles([SOURCE], now=NOW)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(http.call_args.args[0].method, 'GET')
        self.assertFalse(fb.LEDGER_JSON.exists())

    def test_facebook_subtracts_instagram_and_preserves_entry(self):
        ledger = {'months': {'2026-10': {'estimated_spend_usd': 4.5,
            'instagram': {'estimated_spend_usd': .2, 'runs': 1}}}}
        decision = fb.pacing_schedule(ledger, now=NOW, run_cost_usd=.1, budget_usd=5, utilization=.95)
        self.assertTrue(decision['budget_exhausted'])
        fb.record_run(ledger, now=NOW, results=1)
        self.assertAlmostEqual(fb.ledger_month_spend(ledger, NOW), 4.705)

    def test_pipeline_step_and_full_refresh(self):
        with mock.patch.object(run_pipeline, 'execute_step', return_value=0) as execute, \
             mock.patch.object(run_pipeline, 'write_json_atomic'), \
             mock.patch.object(sys, 'argv', ['run_pipeline.py', '--no-lock', '--skip-data-restore', '--full-refresh']):
            self.assertEqual(run_pipeline.main(), 0)
        calls = execute.call_args_list
        index = next(i for i, call in enumerate(calls) if call.kwargs['step'] == 'fetch rsshub')
        self.assertEqual(calls[index + 1].args[0][1:], ['scripts/instagram_public_fetcher.py', '--full-refresh'])
        self.assertTrue(calls[index + 1].kwargs['optional'])

    def test_login_redirect_is_refusal(self):
        client = ig.PublicInstagramClient()
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = 'https://www.instagram.com/accounts/login/?next=/test/'
        with mock.patch.object(client.opener, 'open', return_value=response):
            with self.assertRaises(ig.PublicWebError) as error:
                client.fetch(SOURCE)
        self.assertEqual(error.exception.code, 401)

    def test_shared_budget_skips_paid_run(self):
        ig.feed_common.save_json_atomic(fb.LEDGER_JSON, {'months': {'2026-10': {
            'estimated_spend_usd': 4.749}}})
        with mock.patch.object(ig.urllib.request, 'urlopen') as http:
            with self.assertRaisesRegex(RuntimeError, 'monthly budget'):
                ig.apify_profiles([SOURCE], now=NOW)
        http.assert_not_called()

    def test_failed_paid_request_keeps_reservation(self):
        limits = {'data': {'limits': {'maxMonthlyUsageUsd': 5}, 'current': {'monthlyUsageUsd': 1}}}
        with mock.patch.object(ig.urllib.request, 'urlopen', side_effect=[self.response(limits), TimeoutError()]):
            with self.assertRaises(TimeoutError):
                ig.apify_profiles([SOURCE], now=NOW)
        self.assertEqual(fb.ledger_month_spend(json.loads(fb.LEDGER_JSON.read_text()), NOW), .006)

    def test_dry_run_never_starts_paid_run(self):
        with mock.patch.object(ig.urllib.request, 'urlopen') as http:
            with self.assertRaisesRegex(RuntimeError, 'dry-run'):
                ig.apify_profiles([SOURCE], now=NOW, dry_run=True)
        http.assert_not_called()
        self.assertFalse(fb.LEDGER_JSON.exists())

    def test_apify_preserves_reel_url_and_utc(self):
        profile = {'latestPosts': [{**PROFILE['latestPosts'][0],
            'url': 'https://www.instagram.com/reel/abc/?tracking=1',
            'timestamp': '2026-10-15T20:00:00+08:00'}]}
        row = ig.normalize_profile(SOURCE, profile)[0]
        self.assertEqual(row['id'], 'instagram:https://www.instagram.com/reel/abc/')
        self.assertEqual(row['posted_at'], '2026-10-15T12:00:00+00:00')
