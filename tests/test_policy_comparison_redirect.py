"""Shared questionnaire URLs retain their meaning after comparison integration."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render import policy


@unittest.skipUnless(shutil.which('node'), 'Node is required to execute the browser redirect')
class PolicyComparisonRedirectTests(unittest.TestCase):
    def render_redirect(self, choices=None):
        data = SimpleNamespace(policy_match={'questions': [{'choices': choices or [
            {'id': 'daily-transport', 'topics': ['交通']},
            {'id': 'daily-housing', 'topics': ['住宅', '交通']},
        ]}]})
        with mock.patch.object(policy.S, 'write_page') as write:
            policy.render(data)
        route, html = write.call_args.args
        self.assertEqual(route, '/policy-match/')
        script = re.search(r'<script id="policy-comparison-redirect">(.*?)</script>', html).group(1)
        return script, html

    def run_redirect(self, search='', fragment=''):
        script, _ = self.render_redirect()
        location = {'origin': 'https://mayor2026.observe.tw', 'search': search, 'hash': fragment}
        code = 'const location=' + json.dumps(location) + ';let result;location.replace=value=>{result=value};' + script + ';console.log(result);'
        return subprocess.run(['node', '-e', code], check=True, capture_output=True, text=True).stdout.strip()

    def test_shared_choices_become_unique_topics_and_keep_query(self):
        url = self.run_redirect('?q=社宅&candidates=a,b', '#c=daily-transport,daily-housing')
        from urllib.parse import urlsplit, parse_qs
        parts = urlsplit(url)
        self.assertEqual(parts.path, '/compare/taipei/')
        self.assertEqual(parse_qs(parts.query), {'q': ['社宅'], 'candidates': ['a,b'], 'topics': ['transport,housing']})
        self.assertEqual(parts.fragment, '')

    def test_evidence_anchor_survives_without_quiz_choices(self):
        self.assertEqual(self.run_redirect('?topic=housing', '#source-example'),
                         'https://mayor2026.observe.tw/compare/taipei/?topic=housing#source-example')

    def test_unknown_choices_do_not_create_invalid_topic_filters(self):
        self.assertEqual(self.run_redirect(fragment='#c=obsolete'), 'https://mayor2026.observe.tw/compare/taipei/')

    def test_embedded_mapping_cannot_terminate_script(self):
        script, html = self.render_redirect([{'id': '</script><script>bad()', 'topics': ['交通']}])
        self.assertNotIn('</script>', script)
        self.assertEqual(html.count('</script>'), 1)
        self.assertIn('noindex,follow', html)
        self.assertIn('<noscript>', html)


if __name__ == '__main__':
    unittest.main()
