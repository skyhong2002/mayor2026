"""Isolated callbacks/rendering: synthetic data, no real child/provider/build.

The audit guard is installed before project imports. While fixtures run it
rejects networking, children, dotenv/runtime reads and writes outside their
private temporary directory. Every child command is replaced below; the real
execute_step and nested status callbacks still run.
"""
import contextlib
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_GUARDED = True
_WRITE_ROOT = None


def _guard(event, args):
    if not _GUARDED:
        return
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.posix_spawn", "os.fork", "os.exec", "pty.spawn",
    }:
        raise PermissionError("Synthetic runtime fixture forbids children/network")
    if event == "import" and str(args[0]).startswith((
        "classify_context", "build_status_page", "source_status", "feed_common",
        "apify_", "instagram_", "rsshub_", "youtube_", "official_site_", "publish_",
    )):
        raise PermissionError("Synthetic runtime fixture forbids provider/publisher imports")
    if event == "open":
        raw, mode, flags = args
        if isinstance(raw, int):
            return
        path = Path(raw).resolve()
        if path.name == ".env" or path.name.startswith(".env."):
            raise PermissionError("Synthetic runtime fixture forbids dotenv reads")
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            if _WRITE_ROOT is None or not path.is_relative_to(_WRITE_ROOT):
                raise PermissionError("Synthetic runtime fixture write escaped temporary root")
        elif any(path == ROOT / name or ROOT / name in path.parents for name in ("data", "state", "site", "published")):
            raise PermissionError("Synthetic runtime fixture forbids project runtime reads")
        elif Path('/Users/skyhong/Projects') in path.parents:
            raise PermissionError("Synthetic runtime fixture forbids production reads")
    if event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime"):
        paths = args[:1]
    elif event in ("os.rename", "os.link", "os.symlink"):
        paths = args[:2]
    else:
        return
    for raw in paths:
        if _WRITE_ROOT is None or not Path(raw).resolve().is_relative_to(_WRITE_ROOT):
            raise PermissionError("Synthetic runtime fixture mutation escaped temporary root")


sys.addaudithook(_guard)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "scripts"))
import run_pipeline  # noqa: E402
from render import status as status_page  # noqa: E402
_GUARDED = False


class RuntimeSnapshotTests(unittest.TestCase):
    def setUp(self):
        global _GUARDED, _WRITE_ROOT
        directory = tempfile.TemporaryDirectory(prefix="mayor-runtime-synthetic-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        _WRITE_ROOT, _GUARDED = self.root, True
        self.addCleanup(self.disable_guard)
        self.site = self.root / "site"
        self.site.mkdir()
        self.runtime = self.site / "api/pipeline-runtime.json"
        self.published = self.root / "published"
        self.releases = self.published / "releases"
        self.retained = self.releases / "retained"
        self.retained.mkdir(parents=True)
        (self.retained / "index.html").write_text("synthetic retained release")
        (self.published / "current").symlink_to(self.retained, target_is_directory=True)
        self.transitions = []
        self.publisher_entries = []
        self.snapshots = {}
        self.html_capture = None
        self.children = []

    @staticmethod
    def disable_guard():
        global _GUARDED, _WRITE_ROOT
        _GUARDED, _WRITE_ROOT = False, None

    def run_fixture(self, targets=(), *, failing_target=None, failure_point=None,
                    raises=False, deferred=False, optional_failure=False):
        raw_write = run_pipeline.write_json_atomic
        def write(path, payload):
            self.assertTrue(path.is_relative_to(self.root))
            self.transitions.append(copy.deepcopy(payload))
            raw_write(path, payload)
        def child(command, **kwargs):
            self.assertEqual(kwargs['cwd'], self.root)
            self.children.append(command)
            script = Path(command[1]).stem
            if script == "classify_context" and deferred:
                return subprocess.CompletedProcess(command, 75)
            if script == "fetch_media_cache" and optional_failure:
                return subprocess.CompletedProcess(command, 8)
            if script == "generate_site_pages":
                self.html_capture = json.loads(self.runtime.read_text())
                (self.site / "status.html").write_text(status_page._runtime_block(self.html_capture))
            if script not in ("publish_local", "publish_github_pages"):
                return subprocess.CompletedProcess(command, 0)
            target = "local" if script == "publish_local" else "pages"
            captured = json.loads(self.runtime.read_text())
            self.publisher_entries.append((target, captured, len(self.transitions)))
            def fail(point):
                if target != failing_target or failure_point != point:
                    return False
                if raises:
                    raise OSError("synthetic publisher failure")
                return True
            if fail("before_copy"):
                return subprocess.CompletedProcess(command, 9)
            release = self.releases / target
            shutil.copytree(self.site, release)
            self.snapshots[target] = (release, (release / "api/pipeline-runtime.json").read_bytes())
            if fail("after_copy"):
                return subprocess.CompletedProcess(command, 9)
            if target == "local":
                (self.published / "next").symlink_to(release, target_is_directory=True)
                os.replace(self.published / "next", self.published / "current")
            if fail("after_activation"):
                return subprocess.CompletedProcess(command, 9)
            return subprocess.CompletedProcess(command, 0)
        argv = ["run_pipeline.py", "--skip-watch", "--skip-data-restore", "--no-lock",
                "--runtime-status", str(self.runtime)]
        if "local" in targets:
            argv.append("--publish-local")
        if "pages" in targets:
            argv += ["--publish-pages", "--pages-no-push"]
        with mock.patch.object(run_pipeline, "PROJECT_ROOT", self.root), \
             mock.patch.object(run_pipeline, "write_json_atomic", side_effect=write), \
             mock.patch.object(run_pipeline.pipeline_subprocess, "run", side_effect=child), \
             mock.patch.object(sys, "argv", argv):
            if failing_target:
                with self.assertRaises(OSError if raises else subprocess.CalledProcessError):
                    run_pipeline.main()
            else:
                self.assertEqual(run_pipeline.main(), 0)
        return json.loads(self.runtime.read_text())

    def assert_copies_frozen(self):
        for target, (release, captured_bytes) in self.snapshots.items():
            self.assertEqual((release / "api/pipeline-runtime.json").read_bytes(), captured_bytes)
            captured = json.loads(captured_bytes)
            self.assertEqual(captured["status"], "running")
            expected_step = "publish local snapshot" if target == "local" else "publish github pages"
            self.assertEqual(captured["currentStep"], expected_step)
            self.assertEqual(captured["steps"][-1]["finishedAt"], "")
            self.assertIsNone(captured["steps"][-1]["returnCode"])

    def test_success_is_written_once_after_all_requested_publishers(self):
        for targets in ((), ("local",), ("pages",), ("local", "pages")):
            with self.subTest(targets=targets):
                # Each scenario owns an isolated site; do not overlay a prior copy.
                if self.transitions:
                    self.tearDown(); self.doCleanups(); self.setUp()
                final = self.run_fixture(targets)
                self.assertEqual([p['status'] for p in self.transitions].count("ok"), 1)
                self.assertEqual(self.transitions[-1]['status'], "ok")
                self.assertEqual(final['message'], "Pipeline completed")
                self.assertEqual([t for t, _, _ in self.publisher_entries], list(targets))
                for _, captured, sequence in self.publisher_entries:
                    self.assertEqual(captured['status'], "running")
                    self.assertFalse(any(p['status'] == "ok" for p in self.transitions[:sequence]))
                self.assert_copies_frozen()

    def test_nonzero_local_publication_before_copy_retains_failure(self):
        final = self.run_fixture(("local",), failing_target="local", failure_point="before_copy")
        self.assertEqual(final['status'], "failed")
        self.assertEqual(final['steps'][-1]['status'], "failed")
        self.assertEqual(final['steps'][-1]['returnCode'], 9)
        self.assertFalse(self.snapshots)
        self.assertEqual((self.published/'current').resolve(), self.retained)
        self.assertFalse(any(p['status']=="ok" for p in self.transitions))

    def test_nonzero_after_copy_preserves_copy_and_source_failure(self):
        final = self.run_fixture(("local",), failing_target="local", failure_point="after_copy")
        self.assertEqual(final['status'], "failed")
        self.assertEqual(final['steps'][-1]['returnCode'], 9)
        self.assertEqual((self.published/'current').resolve(), self.retained)
        self.assertFalse(any(p['status']=="ok" for p in self.transitions))
        self.assert_copies_frozen()

    def test_failure_after_activation_does_not_rewrite_activated_snapshot(self):
        final = self.run_fixture(("local",), failing_target="local", failure_point="after_activation")
        self.assertEqual(final['status'], "failed")
        self.assertEqual(final['steps'][-1]['status'], "failed")
        self.assertEqual((self.published/'current').resolve(), self.releases/'local')
        self.assertEqual((self.retained/'index.html').read_text(), "synthetic retained release")
        self.assertFalse(any(p['status']=="ok" for p in self.transitions))
        self.assert_copies_frozen()

    def test_later_pages_failure_keeps_earlier_local_snapshot_historical(self):
        final = self.run_fixture(("local", "pages"), failing_target="pages", failure_point="after_copy")
        self.assertEqual(final['status'], "failed")
        self.assertEqual(final['currentStep'], "publish github pages")
        self.assertEqual(final['steps'][-1]['returnCode'], 9)
        self.assertEqual(final['steps'][-2]['status'], "ok")
        self.assertEqual((self.published/'current').resolve(), self.releases/'local')
        self.assertFalse(any(p['status']=="ok" for p in self.transitions))
        self.assert_copies_frozen()

    def test_publisher_exception_never_claims_completion(self):
        for point in ("before_copy", "after_copy", "after_activation"):
            with self.subTest(point=point):
                if self.transitions:
                    self.tearDown(); self.doCleanups(); self.setUp()
                final = self.run_fixture(("local",), failing_target="local", failure_point=point, raises=True)
                self.assertEqual(final['status'], "failed")
                self.assertEqual(final['currentStep'], "publish local snapshot")
                self.assertNotIn("completed", final['message'].lower())
                self.assertFalse(any(p['status']=="ok" for p in self.transitions))
                self.assert_copies_frozen()

    def test_deferred_and_optional_failure_remain_visible_after_success(self):
        final = self.run_fixture(("local",), deferred=True, optional_failure=True)
        statuses = {step['name']:step for step in final['steps']}
        self.assertEqual(final['status'], "ok")
        self.assertIn("deferred", final['message'])
        self.assertEqual(statuses['classify post topics and posting intent with AI']['status'], "deferred")
        self.assertEqual(statuses['classify post topics and posting intent with AI']['returnCode'],75)
        self.assertEqual(statuses['cache media']['status'],"optional_failed")
        self.assertEqual(statuses['cache media']['returnCode'],8)
        self.assert_copies_frozen()

    def test_html_and_json_keep_their_different_capture_steps(self):
        self.run_fixture(("local",))
        self.assertEqual(self.html_capture['currentStep'], "generate site pages")
        release, raw = self.snapshots['local']
        self.assertEqual(json.loads(raw)['currentStep'], "publish local snapshot")
        html = (release/'status.html').read_text()
        self.assertIn("產生網站頁面", html)
        self.assertIn("擷取時執行中", html)
        self.assertNotIn("發布本機快照", html)

    def test_runtime_labels_are_historical_and_failures_are_preserved(self):
        for state, expected in (("running","擷取時執行中"),("ok","擷取時完成"),("failed","擷取時失敗")):
            with self.subTest(state=state):
                runtime = {'status':state,'currentStep':'<script>bad()</script>',
                    'heartbeatAt':'2000-01-01T00:01:00+00:00','startedAt':'2000-01-01T00:00:00+00:00',
                    'message':'<img src=x onerror=bad()>',
                    'steps':[{'name':'<bad>','status':step,'returnCode':75 if step=='deferred' else 9}
                             for step in ('failed','deferred','optional_failed')]}
                original = copy.deepcopy(runtime)
                html = status_page._runtime_block(runtime)
                self.assertEqual(runtime,original)
                for label in (expected,"擷取時狀態","擷取時步驟","擷取時心跳","擷取時步驟紀錄"):
                    self.assertIn(label,html)
                self.assertNotIn("<script>",html);self.assertNotIn("<img ",html)
                self.assertIn("&lt;script&gt;",html)
                self.assertIn('data-state="error"',html)
                self.assertIn("延後",html);self.assertIn("選用步驟失敗",html)
                self.assertNotIn("目前步驟",html);self.assertNotIn("最近心跳",html)
                if state != 'ok':self.assertNotIn("擷取時完成",html)
        self.assertIn("本快照未擷取",status_page._runtime_block({}))

    def test_static_notice_and_freshness_contract_remain(self):
        html = status_page._headline({'generatedAt':'2000-01-01T00:00:00+00:00',
                                      'overall':{'status':'ok'}})
        for label in ("靜態快照", "不是即時監控", "generatedAt", "8 小時", "不能只依快照"):
            self.assertIn(label,html)

    def test_fixture_guard_blocks_children_network_and_dotenv(self):
        with self.assertRaises(PermissionError):
            subprocess.run([sys.executable,'-c','raise RuntimeError("must not start")'])
        with self.assertRaises(PermissionError):socket.socket()
        with self.assertRaises(PermissionError):(self.root/'.env').read_text()


if __name__ == "__main__":
    unittest.main()
