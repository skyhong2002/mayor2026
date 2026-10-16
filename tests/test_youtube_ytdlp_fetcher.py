import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import source_status
import youtube_ytdlp_fetcher as yt

NOW = dt.datetime(2026, 10, 16, 6, tzinfo=dt.timezone.utc)


def ytdlp_error(video_id, message, warning=False):
    lines = []
    if warning:
        lines.append('WARNING: [youtube] unable to extract yt initial data; please report this issue')
    lines.append(f'ERROR: [youtube] {video_id}: {message}')
    return RuntimeError('\n'.join(lines))


class ClassifyLookupErrorTests(unittest.TestCase):
    def classify(self, error):
        return yt.classify_lookup_error(error, now=NOW)

    def test_deleted_private_and_removed_videos_are_permanent(self):
        for message in ('Video unavailable', 'This video is unavailable', 'Private video',
                        'Video unavailable. This video is not available',
                        'Video unavailable. This video has been removed by the uploader',
                        "Private video. Sign in if you've been granted access to this video."):
            with self.subTest(message=message):
                entry = self.classify(ytdlp_error('abc', message))
                self.assertEqual(entry['status'], 'unavailable')
                self.assertNotIn('retry_after', entry)

    def test_error_after_warning_lines_is_still_recognised(self):
        entry = self.classify(ytdlp_error('abc', 'Private video', warning=True))
        self.assertEqual(entry['status'], 'unavailable')
        self.assertEqual(entry['error'], 'ERROR: [youtube] abc: Private video')

    def test_transient_failures_keep_retrying(self):
        timeout = subprocess.TimeoutExpired(['yt-dlp', 'https://www.youtube.com/watch?v=abc'], 60)
        for error in (timeout, RuntimeError('yt-dlp exited non-zero'),
                      ytdlp_error('abc', "Video unavailable. This content isn't available, try again later."),
                      ytdlp_error('abc', 'Sign in to confirm you’re not a bot. Use --cookies-from-browser'),
                      ytdlp_error('abc', 'Please sign in. Use --cookies-from-browser'),
                      ytdlp_error('abc', 'HTTP Error 429: Too Many Requests'),
                      ytdlp_error('abc', "This video is available to this channel's members"),
                      ytdlp_error('abc', 'Premiere will begin shortly')):
            with self.subTest(error=str(error)):
                self.assertIsNone(self.classify(error))

    def test_upcoming_premieres_retry_after_their_scheduled_time(self):
        cases = {'Premieres in 25 hours': dt.timedelta(hours=25),
                 'Premieres in 3 days': dt.timedelta(days=3),
                 'Premieres in 40 minutes': dt.timedelta(minutes=40),
                 'This live event will begin in 7 hours.': dt.timedelta(hours=7),
                 'This live event will begin in 1 day.': dt.timedelta(days=1)}
        for message, delay in cases.items():
            with self.subTest(message=message):
                entry = self.classify(ytdlp_error('abc', message))
                self.assertEqual(entry['status'], 'upcoming')
                self.assertEqual(entry['retry_after'], source_status.iso(NOW + delay))

    def test_upcoming_without_parsable_time_backs_off_24_hours(self):
        entry = self.classify(ytdlp_error('abc', 'Premieres 10/20/26, 8:00 PM'))
        self.assertEqual(entry['status'], 'upcoming')
        self.assertEqual(entry['retry_after'], source_status.iso(NOW + dt.timedelta(hours=24)))


class BackfillTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        for target, attr, name in ((source_status, 'STATE_PATH', 'state.json'),
                                   (yt.feed_common, 'INBOX_JSONL', 'inbox.jsonl'),
                                   (yt.feed_common, 'CANDIDATES_JSONL', 'candidates.jsonl')):
            patch = mock.patch.object(target, attr, self.dir / name)
            patch.start()
            self.addCleanup(patch.stop)

    def write_inbox(self, rows):
        with yt.feed_common.INBOX_JSONL.open('w', encoding='utf-8') as handle:
            for row in rows:
                handle.write(json.dumps(row) + '\n')

    def run_backfill(self, outcomes, *, now=NOW, limit=10):
        """outcomes maps video id -> posted_at string or an exception to raise."""
        calls = []

        def fake_lookup(video_id):
            calls.append(video_id)
            outcome = outcomes[video_id]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with mock.patch.object(yt, 'fetch_video_posted_at', side_effect=fake_lookup), \
                mock.patch('builtins.print'):
            changed = yt.backfill_missing_dates(limit=limit, now=now)
        return calls, changed

    def videos(self):
        return source_status.load_state().get(yt.LOOKUP_STATE_KEY, {})

    def test_permanent_failures_are_persisted_and_never_looked_up_again(self):
        self.write_inbox([{'id': 'youtube:gone', 'platform': 'youtube', 'posted_at': ''},
                          {'id': 'youtube:flaky', 'platform': 'youtube', 'posted_at': ''}])
        outcomes = {'gone': ytdlp_error('gone', 'Video unavailable'),
                    'flaky': subprocess.TimeoutExpired(['yt-dlp'], 60)}
        calls, _ = self.run_backfill(outcomes)
        self.assertEqual(calls, ['gone', 'flaky'])
        self.assertEqual(self.videos()['gone']['status'], 'unavailable')
        self.assertNotIn('flaky', self.videos())

        calls, _ = self.run_backfill(outcomes, now=NOW + dt.timedelta(days=30))
        self.assertEqual(calls, ['flaky'])

    def test_known_unavailable_rows_do_not_use_up_the_backfill_limit(self):
        self.write_inbox([{'id': 'youtube:gone', 'platform': 'youtube', 'posted_at': ''},
                          {'id': 'youtube:new', 'platform': 'youtube', 'posted_at': ''}])
        source_status.STATE_PATH.write_text(json.dumps({yt.LOOKUP_STATE_KEY: {
            'gone': {'status': 'unavailable', 'error': 'ERROR: Video unavailable'}}}))
        calls, changed = self.run_backfill({'new': '2026-10-15T00:00:00+00:00'}, limit=1)
        self.assertEqual(calls, ['new'])
        self.assertEqual(changed, 1)

    def test_upcoming_premiere_waits_until_it_airs_then_is_forgotten(self):
        self.write_inbox([{'id': 'youtube:soon', 'platform': 'youtube', 'posted_at': ''}])
        calls, _ = self.run_backfill({'soon': ytdlp_error('soon', 'Premieres in 7 hours')})
        self.assertEqual(calls, ['soon'])
        self.assertEqual(self.videos()['soon']['retry_after'], source_status.iso(NOW + dt.timedelta(hours=7)))

        calls, _ = self.run_backfill({}, now=NOW + dt.timedelta(hours=6))
        self.assertEqual(calls, [])

        aired = '2026-10-16T13:00:00+00:00'
        calls, changed = self.run_backfill({'soon': aired}, now=NOW + dt.timedelta(hours=12))
        self.assertEqual((calls, changed), (['soon'], 1))
        self.assertEqual(self.videos(), {})
        row = yt.feed_common.read_jsonl(yt.feed_common.INBOX_JSONL)[0]
        self.assertEqual(row['posted_at'], aired)

    def test_entries_for_rows_that_gained_a_date_are_pruned(self):
        self.write_inbox([{'id': 'youtube:dated', 'platform': 'youtube', 'posted_at': '2026-10-01T00:00:00+00:00'},
                          {'id': 'youtube:gone', 'platform': 'youtube', 'posted_at': ''}])
        source_status.STATE_PATH.write_text(json.dumps({'sources': {'keep': {}}, yt.LOOKUP_STATE_KEY: {
            'dated': {'status': 'upcoming', 'retry_after': source_status.iso(NOW)},
            'gone': {'status': 'unavailable'}}}))
        calls, _ = self.run_backfill({})
        self.assertEqual(calls, [])
        self.assertEqual(set(self.videos()), {'gone'})
        self.assertIn('keep', source_status.load_state()['sources'])


if __name__ == '__main__':
    unittest.main()
