import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import source_status as health
import rsshub_fetcher as rss
import apify_facebook_fetcher as facebook
import build_status_page as status

NOW = dt.datetime(2026, 9, 18, 10, tzinfo=dt.timezone.utc)


def source(sid='test-ig', platform='instagram'):
    return {'id': sid, 'platform': platform, 'candidate_id': 'test', 'candidate_name': '測試',
            'username': sid, 'url': 'https://example.com/' + sid, 'city': 'taipei'}


def account(src, active='true'):
    return {**src, 'account_id': src['id'], 'active': active, 'evidence': '來源查證'}


class SourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.object(health, 'STATE_PATH', Path(self.tmp.name) / 'state.json')
        patch.start()
        self.addCleanup(patch.stop)

    def snapshot(self, src=None, **kwargs):
        src = src or source()
        inputs = dict(accounts=[account(src)], sources=[src], inbox=[], errors=[], apify={}, now=NOW)
        inputs.update(kwargs)
        with mock.patch.object(health.feed_common, 'load_candidates', return_value=[]):
            return health.build_snapshot(**inputs)

    def test_success_clears_failure_and_retry_but_retains_history(self):
        src = source()
        health.record_fetch(src, ok=False, error='HTTP 503', now=NOW)
        health.record_fetch(src, ok=True, items=0, now=NOW + dt.timedelta(hours=6))
        entry = health.load_state()['sources'][src['id']]
        self.assertNotIn('last_error', entry)
        self.assertNotIn('retry_after', entry)
        self.assertEqual(entry['consecutive_failures'], 0)
        self.assertEqual(entry['last_items'], 0)
        self.assertIn('last_error_at', entry)

    def test_unresolved_error_does_not_expire_after_24_hours(self):
        src = source()
        health.record_fetch(src, ok=False, error='still broken', now=NOW - dt.timedelta(days=4))
        row = self.snapshot()['sources'][0]
        self.assertEqual(row['status'], 'error')
        self.assertEqual(row['lastError'], 'still broken')

    def test_backoff_is_bounded_and_retry_ready_uses_persisted_state(self):
        for _ in range(12):
            health.record_fetch(source(), ok=False, error='offline', now=NOW)
        self.assertFalse(health.retry_ready(source(), now=NOW + dt.timedelta(hours=71)))
        self.assertTrue(health.retry_ready(source(), now=NOW + dt.timedelta(hours=72)))

    def test_recovered_legacy_rss_error_is_not_current(self):
        health.STATE_PATH.write_text(json.dumps({'sources': {'test-ig': {
            'last_attempt_at': health.iso(NOW), 'last_success_at': health.iso(NOW),
            'last_error_at': health.iso(NOW - dt.timedelta(hours=8))}}}))
        event = {'source_id': 'test-ig', 'recorded_at': health.iso(NOW - dt.timedelta(hours=8)), 'message': '401'}
        row = self.snapshot(errors=[event])['sources'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['lastError'], '')

    def test_old_inbox_is_not_a_missed_scheduled_fetch(self):
        src = source('yt', 'youtube')
        row = self.snapshot(src, inbox=[{'source_id': 'yt', 'fetched_at': '2026-07-01T00:00:00Z',
            'posted_at': '2026-06-01T00:00:00Z'}])['sources'][0]
        self.assertEqual(row['status'], 'due')
        self.assertIsNone(row['lastAttempt'])
        self.assertEqual(row['contentStatus'], 'quiet')
        self.assertEqual(row['successEvidence'], 'inbox')

    def test_dormant_content_does_not_make_successful_fetch_broken(self):
        src = source('yt', 'youtube')
        health.record_fetch(src, ok=True, items=5, now=NOW)
        row = self.snapshot(src, inbox=[{'source_id': 'yt', 'posted_at': '2026-06-01T00:00:00Z'}])['sources'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['contentStatus'], 'quiet')

    def test_global_cooldown_applies_to_unattempted_instagram_sources(self):
        health.set_instagram_cooldown('401 Unauthorized', now=NOW)
        row = self.snapshot()['sources'][0]
        self.assertEqual(row['status'], 'blocked')
        self.assertEqual(health.parse_time(row['nextEligibleAt']), NOW + dt.timedelta(hours=24))

    def test_disabled_error_is_not_current(self):
        health.record_fetch(source(), ok=False, error='bad', now=NOW)
        row = self.snapshot(accounts=[account(source(), active='false')])['sources'][0]
        self.assertEqual(row['status'], 'disabled')
        self.assertFalse(row['fetchable'])
        self.assertEqual(row['lastError'], '')
        self.assertIsNone(row['nextScheduledAt'])

    def test_no_feed_adapter_is_link_only(self):
        src = {**source('lai-web', 'website'), 'candidate_id': 'lai-jui-lung'}
        row = self.snapshot(src)['sources'][0]
        self.assertEqual(row['status'], 'link_only')
        self.assertFalse(row['fetchable'])

    def test_facebook_normal_budget_wait_is_not_blocked(self):
        src = source('fb', 'facebook')
        row = self.snapshot(src, apify={'ok': True, 'has_token': True,
            'next_eligible_at': health.iso(NOW + dt.timedelta(hours=30)), 'interval_hours': 30})['sources'][0]
        self.assertEqual(row['status'], 'ok')
        self.assertEqual(row['targetIntervalHours'], 30)

    def test_facebook_budget_exhaustion_is_explicit(self):
        src = source('fb', 'facebook')
        row = self.snapshot(src, apify={'ok': True, 'has_token': True, 'budget_exhausted': True,
            'next_eligible_at': '2026-10-01T00:00:00Z'})['sources'][0]
        self.assertEqual(row['status'], 'blocked')
        self.assertIn('下月', row['reason'])

    def test_cadence_tiers_keep_active_and_dormant_accounts_scheduled(self):
        active = [{'posted_at': health.iso(NOW - dt.timedelta(days=i))} for i in range(4)]
        quiet = [{'posted_at': health.iso(NOW - dt.timedelta(days=100 + i))} for i in range(4)]
        self.assertEqual(health.instagram_interval(active, now=NOW), 12)
        self.assertEqual(health.instagram_interval(quiet, now=NOW), 168)

    def test_schedule_converts_to_real_taipei_ticks(self):
        due = dt.datetime(2026, 9, 18, 23, 1, tzinfo=dt.timezone.utc)
        self.assertEqual(health.scheduled_tick(due), dt.datetime(2026, 9, 19, 4, tzinfo=dt.timezone.utc))

    def test_secrets_redacted_from_errors(self):
        self.assertNotIn('secret', health.safe_error('https://api.test/?token=secret&x=1'))

    def test_zero_counts_and_unsafe_html_are_rendered_correctly(self):
        self.assertEqual(status.html_escape(0), '0')
        self.assertEqual(status.html_escape('<script>'), '&lt;script&gt;')

    def test_current_error_annotation_is_not_truncated_to_history_limit(self):
        events = [{'source_id': str(i), 'message': 'bad'} for i in range(35)]
        self.assertEqual(len(status.annotate_errors(events, {})), 35)

    def test_error_history_renders_recovery_status(self):
        for fields, label in (({'resolved': True}, '已恢復'),
                              ({'inactive': True}, '來源已停用／僅連結'),
                              ({'unverified': True}, '歷史紀錄，恢復時間未記錄'),
                              ({}, '尚未恢復')):
            rendered = status.render_error_list([{'message': '<unsafe>', **fields}])
            self.assertIn(label, rendered)
            self.assertNotIn('<unsafe>', rendered)

    def test_rss_401_stops_ig_batch_but_threads_continue(self):
        sources = [source('ig1'), source('ig2'), source('th', 'threads')]
        def fetch(src, **kwargs):
            if src['platform'] == 'instagram':
                raise RuntimeError('HTTP 503: upstream 401 Unauthorized')
            return []
        with mock.patch.object(rss.feed_common, 'load_sources', return_value=sources), \
             mock.patch.object(rss, 'fetch_source', side_effect=fetch) as fetching, \
             mock.patch.object(rss.time, 'sleep'), \
             mock.patch.object(rss.feed_common, 'record_error'), \
             mock.patch.object(rss.feed_common, 'append_jsonl_dedup', return_value=0), \
             mock.patch.object(sys, 'argv', ['rsshub_fetcher.py', '--full-refresh']):
            self.assertEqual(rss.main(), 0)
        ids = [call.args[0]['id'] for call in fetching.call_args_list]
        self.assertIn('th', ids)
        self.assertEqual(len([i for i in ids if i.startswith('ig')]), 1)
        self.assertIn('cooldown_until', health.load_state()['platforms']['instagram'])

    def test_oldest_due_instagram_batch_is_fair_and_bounded(self):
        sources = [source('a'), source('b'), source('c')]
        health.STATE_PATH.write_text(json.dumps({'sources': {
            'a': {'next_eligible_at': '2026-01-03T00:00:00Z'},
            'b': {'next_eligible_at': '2026-01-01T00:00:00Z'},
            'c': {'next_eligible_at': '2026-01-02T00:00:00Z'}}}))
        with mock.patch.object(rss.feed_common, 'load_sources', return_value=sources), \
             mock.patch.object(rss, 'fetch_source', return_value=[]) as fetching, \
             mock.patch.object(rss.time, 'sleep'), \
             mock.patch.object(rss.feed_common, 'append_jsonl_dedup', return_value=0), \
             mock.patch.object(sys, 'argv', ['rsshub_fetcher.py', '--instagram-batch-size', '2']):
            self.assertEqual(rss.main(), 0)
        self.assertEqual([call.args[0]['id'] for call in fetching.call_args_list], ['b', 'c'])

    def test_full_refresh_respects_existing_platform_cooldown(self):
        health.set_instagram_cooldown('429')
        with mock.patch.object(rss.feed_common, 'load_sources', return_value=[source()]), \
             mock.patch.object(rss, 'fetch_source') as fetching, \
             mock.patch.object(sys, 'argv', ['rsshub_fetcher.py', '--full-refresh']):
            self.assertEqual(rss.main(), 0)
        fetching.assert_not_called()

    def test_rss_dry_run_does_not_write_telemetry_or_errors(self):
        with mock.patch.object(rss.feed_common, 'load_sources', return_value=[source()]), \
             mock.patch.object(rss, 'fetch_source', side_effect=TimeoutError('timeout')), \
             mock.patch.object(rss.time, 'sleep'), \
             mock.patch.object(rss.feed_common, 'record_error') as error, \
             mock.patch.object(sys, 'argv', ['rsshub_fetcher.py', '--dry-run']):
            self.assertEqual(rss.main(), 0)
        error.assert_not_called()
        self.assertFalse(health.STATE_PATH.exists())


class FacebookPacingTests(unittest.TestCase):
    def test_structured_due_matches_run_decision(self):
        ledger = {'last_run_at': health.iso(NOW), 'months': {'2026-09': {'estimated_spend_usd': 2.7}}}
        args = dict(now=NOW, run_cost_usd=.21, budget_usd=5, utilization=.95)
        snapshot = facebook.pacing_schedule(ledger, **args)
        self.assertEqual(facebook.dynamic_run_decision(ledger, **args), (snapshot['should_run'], snapshot['reason']))
        self.assertFalse(snapshot['budget_exhausted'])
        self.assertGreater(health.parse_time(snapshot['next_eligible_at']), NOW)

    def test_retry_does_not_start_another_paid_run_immediately(self):
        ledger = {'retry_after': health.iso(NOW + dt.timedelta(hours=6))}
        result = facebook.pacing_schedule(ledger, now=NOW, run_cost_usd=.21, budget_usd=5, utilization=.95)
        self.assertFalse(result['should_run'])
        self.assertIn('retry backoff', result['reason'])


if __name__ == '__main__':
    unittest.main()
