import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_spectrum


class TopicIndexTest(unittest.TestCase):
    @mock.patch.object(build_spectrum.feed_common, "save_json_atomic")
    def test_topic_index_includes_posting_intent(self, save_json_atomic):
        build_spectrum.build_topic_index([
            {
                "id": "post-1",
                "candidate_id": "candidate-1",
                "posted_at": "2026-07-15T00:00:00Z",
                "topic_scores": {"交通": 1.0},
                "postingIntent": {"type": "self_initiated"},
            }
        ])

        payload = save_json_atomic.call_args.args[1]
        self.assertEqual(payload["version"], 2)
        self.assertEqual(payload["posts"][0]["postingIntent"], "self_initiated")


if __name__ == "__main__":
    unittest.main()
