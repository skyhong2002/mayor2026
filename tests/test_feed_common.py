import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import classify_context
import feed_common


class FeedStorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "feed.jsonl"
        self.env = {**os.environ, "PYTHONPATH": str(SCRIPTS)}

    def test_batch_first_occurrence_wins_and_history_bytes_are_preserved(self):
        original = b'{ "id": "old", "text": "original" }\n\n'
        self.path.write_bytes(original)
        count = feed_common.append_jsonl_dedup(self.path, [
            {"id": "old", "text": "replacement"},
            {"id": "new", "text": "first"},
            {"id": "new", "text": "second"},
        ])
        self.assertEqual(count, 1)
        self.assertTrue(self.path.read_bytes().startswith(original))
        self.assertEqual(feed_common.read_jsonl(self.path), [
            {"id": "old", "text": "original"}, {"id": "new", "text": "first"},
        ])
        before = self.path.read_bytes()
        self.assertEqual(feed_common.append_jsonl_dedup(self.path, [{"id": "new"}]), 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_append_adds_missing_separator_without_rewriting_history(self):
        original = '{"id":"old","text":"原文"}'.encode()
        self.path.write_bytes(original)
        feed_common.append_jsonl_dedup(self.path, [{"id": "new"}])
        self.assertTrue(self.path.read_bytes().startswith(original + b"\n"))
        self.assertEqual(len(feed_common.read_jsonl(self.path)), 2)

    def test_failed_batch_serialization_and_corrupt_history_do_not_write(self):
        original = b'{"id":"old"}\n'
        self.path.write_bytes(original)
        with self.assertRaises(TypeError):
            feed_common.append_jsonl_dedup(self.path, [{"id": "good"}, {"id": "bad", "value": object()}])
        self.assertEqual(self.path.read_bytes(), original)
        self.path.write_bytes(b'{"id":')
        with self.assertRaises(json.JSONDecodeError):
            feed_common.append_jsonl_dedup(self.path, [{"id": "new"}])
        self.assertEqual(self.path.read_bytes(), b'{"id":')

    def test_custom_key_and_existing_historical_duplicates_are_preserved(self):
        original = b'{"url":"old","text":"first"}\n{"url":"old","text":"second"}\n'
        self.path.write_bytes(original)
        self.assertEqual(feed_common.append_jsonl_dedup(
            self.path, [{"url": "new"}, {"url": "new"}], key="url"), 1)
        self.assertTrue(self.path.read_bytes().startswith(original))
        self.assertEqual(len(feed_common.read_jsonl(self.path)), 3)

    def test_overlapping_processes_append_each_id_once(self):
        original = b'{ "id": "historical" }\n'
        self.path.write_bytes(original)
        script = """
import sys
from pathlib import Path
import feed_common
index = sys.argv[2]
rows = [{'id': 'shared-' + str(i)} for i in range(25)]
rows += [{'id': index + '-' + str(i)} for i in range(25)]
print(feed_common.append_jsonl_dedup(Path(sys.argv[1]), rows + rows))
"""
        children = [subprocess.Popen([sys.executable, "-c", script, str(self.path), str(i)],
                                    env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for i in range(6)]
        try:
            appended = 0
            for child in children:
                stdout, stderr = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, stderr)
                appended += int(stdout)
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.communicate()
        rows = feed_common.read_jsonl(self.path)
        self.assertEqual(appended, 175)
        self.assertEqual(len(rows), 176)
        self.assertEqual(len({row["id"] for row in rows}), 176)
        self.assertTrue(self.path.read_bytes().startswith(original))

    def test_metadata_fill_waits_for_append_and_preserves_new_rows(self):
        feed_common.append_jsonl_dedup(self.path, [{"id": "old", "posted_at": ""}])
        script = """
import sys
from pathlib import Path
import feed_common
path = Path(sys.argv[1])
with feed_common.jsonl_lock(path):
    print('locked', flush=True)
    sys.stdin.readline()
    with path.open('a') as handle:
        handle.write('{"id":"new","text":"untouched"}\\n')
"""
        writer = subprocess.Popen([sys.executable, "-u", "-c", script, str(self.path)],
                                  env=self.env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        filler = None
        try:
            self.assertEqual(writer.stdout.readline().strip(), "locked")
            fill_script = """
import sys
from pathlib import Path
import feed_common
print('ready', flush=True)
print(feed_common.fill_jsonl_fields(Path(sys.argv[1]), {'old': {'posted_at': '2026-01-01'}}))
"""
            filler = subprocess.Popen([sys.executable, "-u", "-c", fill_script, str(self.path)],
                                      env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(filler.stdout.readline().strip(), "ready")
            with self.assertRaises(subprocess.TimeoutExpired):
                filler.communicate(timeout=0.1)
            writer.communicate("continue\n", timeout=10)
            stdout, stderr = filler.communicate(timeout=10)
            self.assertEqual(filler.returncode, 0, stderr)
            self.assertEqual(stdout.strip(), "1")
        finally:
            for child in [writer, filler]:
                if child is not None:
                    if child.poll() is None:
                        child.kill()
                    child.communicate()
        self.assertEqual(feed_common.read_jsonl(self.path), [
            {"id": "old", "posted_at": "2026-01-01"}, {"id": "new", "text": "untouched"},
        ])

    def test_classifier_save_preserves_concurrent_append_and_source_metadata(self):
        feed_common.append_jsonl_dedup(self.path, [{"id": "old", "text": "原文", "posted_at": ""}])
        snapshot = feed_common.read_jsonl(self.path)
        writer = classify_context.ClassificationWriter(snapshot)
        snapshot[0].update({"classification": {"method": "ai"}, "topics": ["住宅"]})
        feed_common.fill_jsonl_fields(self.path, {"old": {"posted_at": "2026-01-01"}})
        feed_common.append_jsonl_dedup(self.path, [{"id": "new", "text": "後來收錄"}])
        with mock.patch.object(feed_common, "CANDIDATES_JSONL", self.path):
            writer(snapshot)
        rows = feed_common.read_jsonl(self.path)
        self.assertEqual([row["id"] for row in rows], ["old", "new"])
        self.assertEqual(rows[0]["posted_at"], "2026-01-01")
        self.assertEqual(rows[0]["topics"], ["住宅"])
        self.assertEqual(rows[0]["text"], "原文")
        self.assertEqual(rows[1], {"id": "new", "text": "後來收錄"})

    def test_cached_duplicate_ids_are_a_byte_exact_noop(self):
        rows = [{"id": "same", "text": text} for text in ("住宅政策", "交通政策")]
        for row, topic in zip(rows, ("住宅", "交通")):
            classify_context.apply_result(row, {
                "topics": [{"topic": topic, "confidence": .9}],
                "postingIntent": "self_initiated", "intentConfidence": .9,
                "agendaRelevance": .8, "reason": "fixture",
            }, "fixture-model", "fixture-time")
        self.path.write_text("\n".join(json.dumps(row, ensure_ascii=False, indent=None) for row in rows) + "\n")
        before = self.path.read_bytes()
        with mock.patch.object(feed_common, "CANDIDATES_JSONL", self.path), \
             mock.patch.object(classify_context, "run_classification_batch", side_effect=AssertionError("No inference")), \
             mock.patch.object(classify_context, "run_intent_verification_batch", side_effect=AssertionError("No verification")), \
             mock.patch.object(sys, "argv", ["classify_context.py", "--model", "fixture-model"]):
            self.assertEqual(classify_context.main(), 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual([row["topics"] for row in feed_common.read_jsonl(self.path)], [["住宅"], ["交通"]])
        self.assertTrue(all(classify_context.is_current(row, "fixture-model") for row in rows))

    def test_classifier_matches_duplicate_source_content_and_occurrence(self):
        rows = [{"id": "same", "source_id": source, "text": text, "topics": [topic], "nature": "keep"}
                for source, text, topic in (("one", "住宅", "住宅"), ("one", "交通", "交通"),
                                           ("one", "交通", "生活"), ("two", "交通", "交通"))]
        feed_common._replace_jsonl_unlocked(self.path, rows)
        writer = classify_context.ClassificationWriter(rows)
        rows[2]["topics"] = ["環境"]
        with mock.patch.object(feed_common, "CANDIDATES_JSONL", self.path):
            writer(rows)
            # A subsequent no-op save must leave every row untouched.
            before = self.path.read_bytes()
            writer(rows)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(feed_common.read_jsonl(self.path), rows)
        self.assertTrue(all(row["nature"] == "keep" for row in rows))

    def test_classifier_does_not_overwrite_concurrent_classification_or_edited_source(self):
        original = [{"id": "one", "text": "住宅", "topics": ["生活"]},
                    {"id": "two", "text": "交通", "topics": ["生活"]}]
        snapshot = copy.deepcopy(original)
        writer = classify_context.ClassificationWriter(snapshot)
        snapshot[0]["topics"] = ["住宅"]
        snapshot[1]["topics"] = ["交通"]
        latest = copy.deepcopy(original)
        latest[0]["topics"] = ["環境"]
        latest[1]["text"] = "已更新的交通內容"
        feed_common._replace_jsonl_unlocked(self.path, latest)
        before = self.path.read_bytes()
        with mock.patch.object(feed_common, "CANDIDATES_JSONL", self.path):
            writer(snapshot)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
