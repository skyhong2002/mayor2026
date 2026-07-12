import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import classify_context


class ContextClassifierTest(unittest.TestCase):
    def setUp(self):
        self.events = [{"id": "storm", "startAt": "2026-07-01", "endAt": "2026-07-20", "keywords": ["颱風", "停班停課"]}]

    def classify(self, text, at="2026-07-12T00:00:00+08:00"):
        return classify_context.classify({"text": text, "posted_at": at}, self.events)

    def test_external_event_is_independent_from_action(self):
        result = self.classify("颱風來襲，宣布停班停課，請注意安全")
        self.assertEqual(result["trigger"]["type"], "external_event")
        self.assertIn("public_information", result["actions"])

    def test_direct_response_takes_precedence_over_event(self):
        result = self.classify("針對媒體報導的颱風說法，我要澄清")
        self.assertEqual(result["trigger"]["type"], "direct_response")
        self.assertTrue(result["targets"])

    def test_policy_post_is_self_initiated(self):
        result = self.classify("我主張增加社會住宅，將推動新的住宅政策")
        self.assertEqual(result["trigger"]["type"], "self_initiated")
        self.assertIn("policy_proposal", result["actions"])

    def test_unknown_is_not_forced(self):
        result = self.classify("今天與市民朋友見面")
        self.assertEqual(result["trigger"]["type"], "unclear")
        self.assertTrue(result["classification"]["needsReview"])

    def test_event_outside_date_does_not_match(self):
        result = self.classify("颱風來襲", "2026-08-01T00:00:00+08:00")
        self.assertNotEqual(result["trigger"]["type"], "external_event")

    def test_incidental_event_word_deep_in_post_does_not_drive_classification(self):
        text = "本集介紹：" + "地方新聞與政策討論。" * 20 + "最後也談到淹水。"
        result = self.classify(text)
        self.assertNotEqual(result["trigger"]["type"], "external_event")

    def test_policy_signal_beats_routine_word(self):
        result = self.classify("今天行程中，我提出新的住宅政策，未來將推動老屋更新")
        self.assertEqual(result["trigger"]["type"], "self_initiated")


if __name__ == "__main__":
    unittest.main()
