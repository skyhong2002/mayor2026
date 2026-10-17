import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_pipeline


HOLDER = """
import datetime as dt
from pathlib import Path
import sys
import run_pipeline
run_pipeline.utc_now = lambda: dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
path = Path(sys.argv[1])
locked = run_pipeline.acquire_lock(path, stale_after_minutes=1)
print('held' if locked else 'busy', flush=True)
if locked:
    sys.stdin.readline()
    run_pipeline.release_lock(path)
"""


class PipelineLockTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "pipeline.lock"
        self.addCleanup(run_pipeline.release_lock, self.path)
        self.env = {**os.environ, "PYTHONPATH": str(SCRIPTS)}

    def start_holder(self):
        child = subprocess.Popen([sys.executable, "-u", "-c", HOLDER, str(self.path)],
                                 env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_child, child)
        self.assertEqual(child.stdout.readline().strip(), "held")
        return child

    @staticmethod
    def stop_child(child):
        if child.poll() is None:
            child.kill()
        child.communicate()

    def test_live_owner_is_never_evicted_by_age_and_release_keeps_inode(self):
        child = self.start_holder()
        inode = self.path.stat().st_ino
        self.assertEqual(json.loads(self.path.read_text())["started_at"], "2000-01-01T00:00:00+00:00")
        self.assertFalse(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
        child.communicate("finish\n", timeout=10)
        self.assertTrue(self.path.exists())
        self.assertEqual(self.path.stat().st_ino, inode)
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
        self.assertFalse(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
        run_pipeline.release_lock(self.path)
        self.assertEqual(self.path.stat().st_ino, inode)

    def test_killed_owner_releases_lock_without_unlinking_or_waiting(self):
        child = self.start_holder()
        inode = self.path.stat().st_ino
        child.kill()
        child.communicate(timeout=10)
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=240))
        self.assertEqual(self.path.stat().st_ino, inode)

    def test_pre_upgrade_live_pid_is_respected_even_when_timestamp_is_old(self):
        original = json.dumps({"pid": os.getpid(), "started_at": "2000-01-01T00:00:00Z"})
        self.path.write_text(original)
        self.assertFalse(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
        self.assertEqual(self.path.read_text(), original)
        self.path.write_text('{"pid": 0, "started_at": "2000-01-01T00:00:00Z"}')
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))

    def test_corrupt_or_empty_abandoned_metadata_does_not_wedge_pipeline(self):
        self.path.write_text('{"pid":')
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
        run_pipeline.release_lock(self.path)
        self.path.write_text("")
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))

    def test_active_stage_keeps_lock_when_controller_is_killed(self):
        stage = "import os,sys; print('stage:' + str(os.getpid()), flush=True); sys.stdin.readline()"
        controller = """
from pathlib import Path
import sys
import run_pipeline
assert run_pipeline.acquire_lock(Path(sys.argv[1]), stale_after_minutes=1)
run_pipeline.execute_step([sys.executable, '-u', '-c', sys.argv[2]], step='fixture', mark_step=lambda *a, **kw: None)
"""
        child = subprocess.Popen([sys.executable, "-u", "-c", controller, str(self.path), stage],
                                 env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        stage_pid = None
        try:
            line = child.stdout.readline().strip()
            self.assertTrue(line.startswith("stage:"), line)
            stage_pid = int(line.split(":")[1])
            child.kill()
            child.wait(timeout=10)
            self.assertFalse(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))
            child.communicate("finish\n", timeout=10)
            deadline = time.monotonic() + 5
            while not run_pipeline.acquire_lock(self.path, stale_after_minutes=1):
                if time.monotonic() > deadline:
                    self.fail("Stage did not release its inherited lock")
                time.sleep(0.01)
            stage_pid = None
        finally:
            if stage_pid is not None:
                try:
                    os.kill(stage_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.stop_child(child)

    def test_status_write_failure_releases_acquired_lock(self):
        argv = ["run_pipeline.py", "--lock-file", str(self.path)]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(run_pipeline, "write_json_atomic", side_effect=OSError("fixture failure")):
            with self.assertRaisesRegex(OSError, "fixture failure"):
                run_pipeline.main()
        self.assertTrue(run_pipeline.acquire_lock(self.path, stale_after_minutes=1))


if __name__ == "__main__":
    unittest.main()
