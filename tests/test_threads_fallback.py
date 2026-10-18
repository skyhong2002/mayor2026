"""Focused AST/fake public transport tests; no product/config/network imports."""
from __future__ import annotations

import ast
import contextlib
import datetime as dt
import email.utils
import html
import http.cookiejar
import io
import json
from pathlib import Path
import re
import socket
import ssl
import sys
from types import SimpleNamespace
from typing import Any
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


PROFILE = b'"LSD",[],{"token":"PUBLIC_SYNTHETIC"};"initial_thread_count":5,"user_id":"123"'
SCRIPT = b'BarcelonaProfileThreadsTabRefetchableDirectQuery_threadsRelayOperation" exports="555" name:"__relay_internal__pv__BarcelonaHasCommunitiesrelayprovider"'


def payload(*posts):
    return {"data": {"mediaData": {"edges": [{"node": {"thread_items": [{"post": post} for post in posts]}}]}}}


def post(code="ABC123", username="example", **kwargs):
    return {"pk": "987654321", "code": code, "user": {"username": username},
            "taken_at": 1700000000, "caption": {"text": "synthetic announcement"}, **kwargs}


class Response:
    def __init__(self, data=b"", headers=None):
        self.data = data.encode() if isinstance(data, str) else data
        self.headers = headers or {}
        self.status = 200
        self.closed = False

    def read(self, size):
        raw, self.data = self.data[:size], self.data[size:]
        return raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class Fixture(unittest.TestCase):
    def setUp(self):
        for owner, name in ((socket, "socket"), (socket, "getaddrinfo"),
                            (socket, "create_connection"), (ssl, "SSLContext")):
            guard = patch.object(owner, name, side_effect=AssertionError("real network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.now = 0
        self.actions, self.calls, self.health, self.errors, self.appended = [], [], [], [], []
        owner = self

        class Opener:
            def open(self, request, timeout):
                owner.calls.append((request, timeout))
                action = owner.actions.pop(0)
                if isinstance(action, tuple):
                    action, duration = action
                    owner.now += duration
                if isinstance(action, Exception):
                    raise action
                return action

        self.opener = Opener()
        self.build = patch.object(urllib.request, "build_opener", return_value=self.opener)
        self.build.start()
        self.addCleanup(self.build.stop)
        self.source = {"id": "synthetic-source", "platform": "threads", "username": "example",
                       "candidate_id": "synthetic-candidate", "city": "taipei"}
        feed = SimpleNamespace(strip_html=lambda text: re.sub(r"<[^>]*>", "", text),
                               utc_now_iso=lambda: "2026-10-18T00:00:00+00:00",
                               load_sources=lambda **kwargs: [self.source],
                               append_jsonl_dedup=lambda path, rows: self.appended.extend(rows) or len(rows),
                               record_error=lambda *args: self.errors.append(args),
                               INBOX_JSONL=Path("/synthetic/inbox"), PROJECT_ROOT=Path("/synthetic"))
        health = SimpleNamespace(retry_ready=lambda source, **kw: True,
                                 record_fetch=lambda source, **kw: self.health.append(kw),
                                 safe_error=lambda error: str(error))
        self.ns = {"argparse": __import__("argparse"), "dt": dt, "email": email, "html": html,
                   "http": http, "json": json, "re": re,
                   "time": SimpleNamespace(monotonic=lambda: self.now, sleep=lambda _: None),
                   "urllib": urllib, "ET": ET, "Any": Any, "feed_common": feed,
                   "source_status": health, "DEFAULT_RSSHUB_BASE": "https://rss.invalid"}
        path = Path(__file__).resolve().parents[1] / "scripts/rsshub_fetcher.py"
        tree = ast.parse(path.read_text())
        nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                 or isinstance(node, ast.Assign) and all(isinstance(t, ast.Name)
                    and t.id != "DEFAULT_RSSHUB_BASE" for t in node.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), self.ns)

    def graphql_actions(self, profile=PROFILE, posts=None):
        return [Response(profile), Response(json.dumps(payload(*(posts or [post()]))))]

    def fetch(self, **kwargs):
        return self.ns["fetch_source"](self.source, rsshub_base="https://rss.invalid", limit=kwargs.get("limit", 10))

    def http_error(self, url="https://rss.invalid/threads/example", code=503, location=None):
        body = io.BytesIO(b"synthetic upstream undefined.url")
        error = urllib.error.HTTPError(url, code, "synthetic", {"Location": location} if location else {}, body)
        return error, body


class ThreadsFallbackTests(Fixture):
    def test_healthy_rsshub_never_calls_public_fallback(self):
        self.actions = [Response("<rss><channel><item><guid>https://www.threads.com/t/ABC123</guid><link>https://www.threads.com/@example/post/ABC123</link></item></channel></rss>")]
        rows = self.fetch()
        self.assertEqual(rows[0]["id"], "threads:https://www.threads.com/t/ABC123")
        self.assertEqual(len(self.calls), 1)

    def test_http_rsshub_failure_uses_one_public_query(self):
        error, body = self.http_error()
        self.actions = [error, *self.graphql_actions()]
        rows = self.fetch()
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(self.calls), 3)
        self.assertEqual([req.get_method() for req, _ in self.calls], ["GET", "GET", "POST"])
        self.assertTrue(body.closed)

    def test_bad_xml_uses_fallback_but_empty_valid_feed_does_not(self):
        self.actions = [Response(b"broken"), *self.graphql_actions()]
        self.assertEqual(len(self.fetch()), 1)
        before = len(self.calls)
        self.actions = [Response("<rss><channel/></rss>")]
        self.assertEqual(self.fetch(), [])
        self.assertEqual(len(self.calls), before + 1)

    def test_canonical_profile_redirect_updates_query_origin(self):
        error, body = self.http_error("https://www.threads.com/@example", 301, "https://threads.com/@example/")
        self.actions = [error, *self.graphql_actions()]
        rows = self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(rows), 1)
        self.assertTrue(body.closed)
        query = self.calls[-1][0]
        self.assertEqual(query.full_url, "https://threads.com/graphql/query")
        self.assertEqual(query.get_header("Origin"), "https://threads.com")
        self.assertEqual(self.calls[1][0].get_header("X-fb-lsd"), None)

    def test_profile_redirects_reject_cross_host_user_credentials_query_and_http(self):
        redirect = self.ns["_threads_profile_redirect"]
        for target in ("https://evil.example/@example", "http://threads.com/@example", "https://threads.com/@other",
                       "https://user:pass@threads.com/@example", "https://threads.com:444/@example",
                       "https://threads.com/@example?token=x", "https://threads.com/@example#x"):
            with self.subTest(target=target), self.assertRaises(RuntimeError):
                redirect("https://www.threads.com/@example", target)

    def test_profile_redirect_budget_no_fourth_request(self):
        errors = [self.http_error("https://www.threads.com/@example", 302, "https://threads.com/@example")[0] for _ in range(3)]
        self.actions = errors
        with self.assertRaises(RuntimeError):
            self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 3)

    def test_combined_source_request_bound_includes_two_profile_redirects(self):
        rss, _ = self.http_error()
        redirect1, _ = self.http_error("https://www.threads.com/@example", 301, "https://threads.com/@example")
        redirect2, _ = self.http_error("https://threads.com/@example", 301, "https://www.threads.com/@example/")
        profile = PROFILE + b'<script src="https://static.cdninstagram.com/one.js"></script><script src="https://static.cdninstagram.com/two.js"></script>'
        self.actions = [rss, redirect1, redirect2, Response(profile), Response(b"none"),
                        Response(b"none"), Response(json.dumps(payload(post())))]
        self.assertEqual(len(self.fetch()), 1)
        self.assertEqual(len(self.calls), 7)

    def test_post_and_cdn_redirects_are_not_followed(self):
        error, body = self.http_error("https://www.threads.com/graphql/query", 307, "https://threads.com/graphql/query")
        self.actions = [Response(PROFILE), error]
        with self.assertRaises(RuntimeError):
            self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(body.closed)
        error, body = self.http_error("https://static.cdninstagram.com/one.js", 302, "https://evil.example/script.js")
        profile = PROFILE + b'<script src="https://static.cdninstagram.com/one.js"></script>'
        self.actions = [Response(profile), error, Response(json.dumps(payload(post())))]
        self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 5)
        self.assertTrue(body.closed)
        self.assertFalse(any("evil.example" in req.full_url for req, _ in self.calls))

    def test_only_two_cdn_scripts_and_no_ephemeral_headers(self):
        profile = PROFILE + b''.join(f'<script src="https://static.cdninstagram.com/{i}.js"></script>'.encode() for i in range(5))
        self.actions = [Response(profile), Response(b"no metadata"), Response(b"no metadata"), Response(json.dumps(payload(post())))]
        self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual([r.full_url for r, _ in self.calls[1:3]], ["https://static.cdninstagram.com/4.js", "https://static.cdninstagram.com/3.js"])
        for request, _ in self.calls[1:3]:
            self.assertEqual(set(dict(request.header_items())), {"User-agent", "Accept-encoding"})
        form = urllib.parse.parse_qs(self.calls[-1][0].data.decode())
        self.assertEqual(form["doc_id"], [self.ns["THREADS_GRAPHQL_FALLBACK_DOC_ID"]])

    def test_query_metadata_is_cached_without_profile_tokens(self):
        profile = PROFILE + b'<script src="https://static.cdninstagram.com/current.js"></script>'
        self.actions = [Response(profile), Response(SCRIPT), Response(json.dumps(payload(post()))), *self.graphql_actions(profile)]
        self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 5)
        self.assertNotIn("PUBLIC_SYNTHETIC", repr(self.ns["_THREADS_QUERY_METADATA_CACHE"]))
        self.assertEqual(urllib.parse.parse_qs(self.calls[-1][0].data.decode())["doc_id"], ["555"])

    def test_budget_spans_rsshub_and_public_requests(self):
        self.actions = [(Response(b"broken"), 21), (Response(PROFILE), 9)]
        with self.assertRaises(RuntimeError):
            self.fetch()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([timeout for _, timeout in self.calls], [10, 9])

    def test_response_cap_and_compression_fail_without_query(self):
        self.ns["THREADS_MAX_RESPONSE_BYTES"] = 20
        response = Response(b"x" * 21)
        self.actions = [response]
        with self.assertRaises(RuntimeError):
            self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertTrue(response.closed)
        self.assertEqual(len(self.calls), 1)
        self.actions = [Response(PROFILE, {"Content-Encoding": "gzip"})]
        with self.assertRaises(RuntimeError):
            self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 2)

    def test_normalization_preserves_legacy_id_and_avoids_duplicate_insert(self):
        root = ET.fromstring("<rss><channel><item><guid>https://www.threads.com/t/ABC123</guid></item></channel></rss>")
        legacy = self.ns["normalize_items"](self.source, root, limit=10)
        direct = self.ns["normalize_threads_posts"](self.source, payload(post()), limit=10)
        self.assertEqual(legacy[0]["id"], direct[0]["id"])
        self.assertEqual(len({row["id"] for row in legacy + direct}), 1)
        self.assertNotIn("987654321", direct[0]["id"])

    def test_normalization_keeps_authored_unique_posts_media_and_limit(self):
        media = {"image_versions2": {"candidates": [{"url": "https://cdn.example/image.jpg"}]},
                 "video_versions": [{"url": "https://cdn.example/video.mp4"}]}
        rows = self.ns["normalize_threads_posts"](self.source, payload(post(**media), post(), post("REPLY", "other"), post("SECOND")), limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["media"], ["https://cdn.example/image.jpg", "https://cdn.example/video.mp4"])
        self.assertEqual(rows[0]["posted_at"], "2023-11-14T22:13:20+00:00")
        self.assertEqual(len(self.ns["normalize_threads_posts"](self.source, payload(*[post(str(i)) for i in range(20)]), limit=100)), 15)

    def test_invalid_media_and_code_do_not_make_unsafe_rows(self):
        bad_media = {"image_versions2": {"candidates": [{"url": "javascript:alert(1)"}]}}
        rows = self.ns["normalize_threads_posts"](self.source, payload(post(**bad_media), post("../../bad"), {"code": "MISSINGAUTHOR"}), limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["media"], [])

    def test_missing_errors_and_malformed_shapes_are_not_empty_success(self):
        for value in ({}, {"errors": [{"message": "PRIVATE_SYNTHETIC"}]}, {"data": {"mediaData": {"edges": [None]}}}, []):
            with self.subTest(shape=type(value).__name__), self.assertRaises(RuntimeError) as caught:
                self.ns["normalize_threads_posts"](self.source, value, limit=1)
            self.assertNotIn("PRIVATE_SYNTHETIC", str(caught.exception))
        self.assertEqual(self.ns["normalize_threads_posts"](self.source, {"data": {"mediaData": {"edges": []}}}, limit=1), [])

    def test_missing_profile_metadata_never_requests_query(self):
        self.actions = [Response(b"logged out page without metadata")]
        with self.assertRaises(RuntimeError):
            self.ns["fetch_threads_graphql"](self.source, limit=1)
        self.assertEqual(len(self.calls), 1)

    def test_invalid_username_makes_no_request(self):
        for username in ("../other", "user?token=x", "a/b", "@", "a" * 31):
            with self.assertRaises(RuntimeError):
                self.ns["fetch_threads_graphql"]({**self.source, "username": username}, limit=1)
        self.assertEqual(self.calls, [])

    def test_aggregate_probe_does_not_expose_content_or_write(self):
        self.actions = self.graphql_actions()
        result = self.ns["probe_threads_source"](self.source)
        self.assertEqual(result, {"backend": "Threads public logged-out", "rows": 1,
                                 "rows_with_valid_time": 1, "rows_with_media": 0,
                                 "state_or_inbox_written": False})
        self.assertNotIn("ABC123", json.dumps(result))
        self.assertNotIn("PUBLIC_SYNTHETIC", json.dumps(result))
        self.assertEqual((self.health, self.errors, self.appended), ([], [], []))

    def test_x_and_podcast_stay_on_original_adapter(self):
        calls = []
        self.ns["fetch_rss"] = lambda url: calls.append(url) or ET.fromstring("<rss><channel/></rss>")
        for source in ({**self.source, "platform": "x"}, {**self.source, "platform": "podcast", "feed_url": "https://podcast.invalid/feed"}):
            self.assertEqual(self.ns["fetch_source"](source, rsshub_base="https://rss.invalid", limit=10), [])
        self.assertEqual(calls, ["https://rss.invalid/twitter/user/example", "https://podcast.invalid/feed"])
        self.assertEqual(self.calls, [])

    def test_source_backoff_prevents_all_rsshub_and_public_calls(self):
        self.ns["source_status"].retry_ready = lambda *args, **kw: False
        with patch.object(sys, "argv", ["rsshub_fetcher.py"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.ns["main"](), 0)
        self.assertEqual((self.calls, self.health, self.errors), ([], [], []))

    def test_both_fail_records_real_failure_without_clearing_state(self):
        error, _ = self.http_error()
        self.actions = [error, Response(b"no profile metadata")]
        with patch.object(sys, "argv", ["rsshub_fetcher.py"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.ns["main"](), 0)
        self.assertEqual(len(self.health), 1)
        self.assertIs(self.health[0]["ok"], False)
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.appended, [])


if __name__ == "__main__":
    unittest.main()
