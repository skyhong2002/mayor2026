import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import build_issue_comparisons as B
from render import comparison


def fixture():
    candidates = [{"id": f"c{i}", "number": i, "name": f"候選人{i}", "party": "無黨籍",
                   "rosterSource": "https://example.test/roster"} for i in range(1, 7)]
    source = {"id": "s1", "candidateId": "c1", "title": "住宅政策", "text": "我們主張新增一千戶社宅，須先取得中央經費。",
              "url": "https://example.test/policy", "postedAt": "2026-11-01", "kind": "policy", "platform": "website",
              "headings": [{"level": "h1", "text": "住宅政策"}, {"level": "h3", "text": "社宅財源與條件"}],
              "alternatives": [{"url": "https://example.test/policy", "platform": "website"}]}
    post = {**source, "id": "s2", "kind": "post", "title": "本人貼文", "headings": [], "platform": "facebook"}
    claim = {"id": "a1", "sourceId": "s1", "candidateId": "c1", "topic": "住宅", "subtopic": "社宅興建",
             "sourceHeading": "社宅財源與條件", "summary": "主張新增一千戶社宅，但以取得中央經費為前提。",
             "assertionType": "政策承諾", "quote": source["text"], "conditions": "須先取得中央經費"}
    question = {"id": "housing-1", "title": "如何興建社宅？", "claimIds": ["a1"], "relation": "尚無法比較",
                "summary": "目前只有候選人1提出有條件的社宅興建主張。", "summaryVerified": True,
                "rows": [{"candidateId": "c1", "summary": claim["summary"], "claimIds": ["a1"], "verified": True}]}
    return {"candidates": candidates, "sources": [source, post], "claims": [claim],
            "topics": [{"id": slug, "name": topic, "questions": [question] if topic == "住宅" else [],
                        "provenance": [{"model": "model-reported"}]} for topic, slug in B.TOPICS.items()],
            "limitations": ["僅代表收錄範圍"], "rawSourceCount": 2, "generatedAt": "2026-11-16", "analysisAt": "2026-11-16",
            "extractionProvenance": [{"reviewed": ["s1", "s2"]}]}


class ComparisonIntegrityTests(unittest.TestCase):
    def test_complete_snapshot(self):
        B.validate_snapshot(fixture())

    def test_missing_candidate_cannot_be_published(self):
        data = fixture()
        data["candidates"].pop()
        with self.assertRaisesRegex(ValueError, "six"):
            B.validate_snapshot(data)

    def test_missing_topic_cannot_be_published(self):
        data = fixture()
        data["topics"].pop()
        with self.assertRaisesRegex(ValueError, "topics"):
            B.validate_snapshot(data)

    def test_unread_source_cannot_be_published(self):
        data = fixture()
        data["extractionProvenance"][0]["reviewed"] = ["s1"]
        with self.assertRaisesRegex(ValueError, "not all source"):
            B.validate_snapshot(data)

    def test_topic_brief_must_reference_existing_claims(self):
        data = fixture()
        data["topics"][1]["briefFindings"] = [{"text": "summary", "claimIds": ["unknown"], "verified": True}]
        with self.assertRaisesRegex(ValueError, "brief evidence"):
            B.validate_snapshot(data)

    def test_failed_topic_brief_is_not_in_the_public_page_or_json(self):
        data = fixture()
        next(t for t in data["topics"] if t["id"] == "housing")["briefFindings"] = [
            {"text": "Rejected topic-level conclusion", "claimIds": ["a1"], "verified": False},
            {"text": "Verified topic-level conclusion", "claimIds": ["a1"], "verified": True}]
        with tempfile.TemporaryDirectory() as tmp:
            comparison.render_review(data, Path(tmp))
            html = (Path(tmp) / "compare/taipei/index.html").read_text()
            public_json = (Path(tmp) / "api/comparison.json").read_text()
        self.assertNotIn("Rejected topic-level conclusion", html + public_json)
        self.assertIn("Verified topic-level conclusion", public_json)
        self.assertIn('id="claim-a1"', html)

    def test_table_copy_removes_editorial_asides_but_keeps_policy_conditions(self):
        value = "研擬加碼5至10%補貼，須先取得中央經費。兩次說法的範圍需核對，不能直接視為同一指標。本題引文未提上路時程。"
        self.assertEqual(comparison.position_copy(value), "研擬加碼5至10%補貼，須先取得中央經費。")
        self.assertEqual(comparison.position_copy("主張重劃交通標線，不能只靠開罰處理問題。"), "主張重劃交通標線，不能只靠開罰處理問題。")

    def test_table_associates_every_candidate_cell_with_its_column_and_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            comparison.render_review(fixture(), Path(tmp))
            html = (Path(tmp) / "compare/taipei/index.html").read_text()
        self.assertIn('<table class="comparison-table">', html)
        self.assertIn('data-topic-filter=', html)
        self.assertIn('選擇要比較的議題，可複選', html)
        self.assertNotIn('data-topic-button', html)
        self.assertNotIn('role="tab', html)
        self.assertIn('scope="row" class="question-label" id="housing-1-title"', html)
        for i in range(1, 7):
            self.assertIn(f'headers="candidate-c{i} housing-1-title"', html)

    def test_candidate_columns_sort_by_post_count_excluding_policy_pages(self):
        data = fixture()
        post = data["sources"][1]
        data["sources"].extend({**post, "id": f"p{i}", "candidateId": "c2"} for i in range(2))
        data["sources"].extend({**data["sources"][0], "id": f"policy{i}", "candidateId": "c3"} for i in range(5))
        with tempfile.TemporaryDirectory() as tmp:
            comparison.render_review(data, Path(tmp))
            html = (Path(tmp) / "compare/taipei/index.html").read_text()
            public = json.loads((Path(tmp) / "api/comparison.json").read_text())
        self.assertEqual([c["id"] for c in public["candidates"]], ["c2", "c1", "c3", "c4", "c5", "c6"])
        self.assertEqual([c["number"] for c in public["candidates"]], [2, 1, 3, 4, 5, 6])
        for marker in ('id="candidate-', 'data-candidate-filter="', 'headers="candidate-'):
            self.assertLess(html.index(marker + 'c2'), html.index(marker + 'c1'))
            self.assertLess(html.index(marker + 'c1'), html.index(marker + 'c3'))

    def test_production_render_preserves_home_and_robots_and_keeps_local_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text("existing homepage")
            (root / "robots.txt").write_text("User-agent: *\nAllow: /\n")
            comparison.render_review(fixture(), root, review=False)
            html = (root / "compare/taipei/index.html").read_text()
            self.assertEqual((root / "index.html").read_text(), "existing homepage")
            self.assertEqual((root / "robots.txt").read_text(), "User-agent: *\nAllow: /\n")
        self.assertNotIn("noindex", html)
        self.assertNotIn("・Review", html)
        self.assertIn('href="/"', html)
        self.assertIn('href="/compare/taipei/"', html)

    def test_missing_production_snapshot_fails_without_touching_existing_pages(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(comparison.S, "PROJECT_ROOT", Path(tmp)):
            with mock.patch.object(comparison, "render_review") as render:
                with self.assertRaises(FileNotFoundError):
                    comparison.render(None)
            render.assert_not_called()

    def test_quote_not_in_source_is_rejected(self):
        data = fixture()
        data["claims"][0]["quote"] = "我反對興建社會住宅"
        with self.assertRaisesRegex(ValueError, "evidence"):
            B.validate_snapshot(data)

    def test_wrong_candidate_attribution_is_rejected(self):
        data = fixture()
        q = next(t for t in data["topics"] if t["id"] == "housing")["questions"][0]
        q["rows"][0]["candidateId"] = "c2"
        with self.assertRaisesRegex(ValueError, "attribution"):
            B.validate_snapshot(data)

    def test_one_person_is_not_a_disagreement(self):
        data = fixture()
        q = next(t for t in data["topics"] if t["id"] == "housing")["questions"][0]
        q["relation"] = "明確分歧"
        with self.assertRaisesRegex(ValueError, "two"):
            B.validate_snapshot(data)

    def test_every_claim_must_be_in_a_question(self):
        data = fixture()
        next(t for t in data["topics"] if t["id"] == "housing")["questions"] = []
        with self.assertRaisesRegex(ValueError, "omitted"):
            B.validate_snapshot(data)

    def test_source_split_never_silently_truncates_text(self):
        source = {"id": "s", "text": "甲" * 500 + "\n" + "乙" * 1700 + "\n" + "丙" * 300}
        chunks = B.split_source(source, 650)
        self.assertTrue(all(len(c["text"]) <= 650 for c in chunks))
        self.assertTrue(all(c["parentId"] == "s" for c in chunks))
        self.assertIn("丙" * 300, "".join(c["text"] for c in chunks))
        self.assertGreaterEqual(sum(c["text"].count("乙") for c in chunks), 1700)

    def test_parser_keeps_all_article_headings_without_navigation(self):
        parser = B.PolicyHTML()
        parser.feed('<nav><h2>導航</h2></nav><article class="policy-page"><h1>住宅</h1><h2>措施</h2><h3>財源</h3><p>有條件支持</p></article><footer><h3>頁尾</h3></footer>')
        self.assertEqual([h["text"] for h in parser.headings], ["住宅", "措施", "財源"])
        self.assertNotIn("導航", parser.text())
        self.assertNotIn("頁尾", parser.text())

    def test_failed_summaries_are_hidden_but_direct_evidence_is_retained(self):
        data = fixture()
        q = next(t for t in data["topics"] if t["id"] == "housing")["questions"][0]
        q.update(summary="UNSUPPORTED-COMPARISON", summaryVerified=False)
        q["rows"][0].update(summary="UNSUPPORTED-POSITION", verified=False)
        with tempfile.TemporaryDirectory() as tmp:
            comparison.render_review(data, Path(tmp))
            html = (Path(tmp) / "compare/taipei/index.html").read_text()
            public_json = (Path(tmp) / "api/comparison.json").read_text()
        # Original rejected text is not even in searchable HTML attributes.
        self.assertNotIn("unsupported-comparison", html.lower())
        self.assertNotIn("unsupported-position", html.lower())
        self.assertNotIn("unsupported-comparison", public_json.lower())
        self.assertNotIn("unsupported-position", public_json.lower())
        self.assertIn(data["claims"][0]["quote"], html)
        self.assertIn("來源尚未取得", html)
        self.assertIn("社宅財源與條件", html)
        for c in data["candidates"]:
            self.assertIn(c["name"], html)

    def test_original_text_is_escaped_and_script_urls_are_not_linked(self):
        data = fixture()
        data["sources"][1]["text"] = '<script>alert("source")</script>'
        data["sources"][1]["url"] = 'javascript:alert("url")'
        with tempfile.TemporaryDirectory() as tmp:
            comparison.render_review(data, Path(tmp))
            html = (Path(tmp) / "compare/taipei/index.html").read_text()
        self.assertNotIn('<script>alert("source")</script>', html)
        self.assertNotIn('href="javascript:', html)
        self.assertIn('&lt;script&gt;', html)

    def test_display_dates_use_taipei_timezone(self):
        self.assertEqual(comparison.day("2026-11-15T17:00:00+00:00"), "2026-11-16")
        self.assertEqual(comparison.day("2026-11-15"), "2026-11-15")

    def test_alignment_preserves_both_candidates_and_decodes_opaque_references(self):
        data = fixture()
        first = {**data["claims"][0], "topic": "交通", "subtopic": "環城線續推", "summary": "支持現案", "quote": "支持現案"}
        second = {**first, "id": "a2", "candidateId": "c2", "sourceId": "s2", "subtopic": "環城線改線", "summary": "反對現案", "quote": "反對現案"}
        data["sources"][0]["text"] = "支持現案"
        data["sources"][1].update(candidateId="c2", text="反對現案")

        def fake_request(stage, instructions, payload, schema, max_output=16000):
            if stage == "align":
                result = {"groups": [{"title": "是否支持環城線現案？", "labels": [first["subtopic"], second["subtopic"]]}]}
            elif stage == "compare":
                rows = payload["groups"][0]["claims"]
                self.assertEqual([r["id"] for r in rows], ["c0", "c1"])
                self.assertEqual({r["candidateId"] for r in rows}, {"c1", "c2"})
                result = {"questions": [{"title": "是否支持環城線現案？", "claimIds": ["c0", "c1"], "relation": "明確分歧",
                    "summary": "兩位候選人對現案支持與反對。", "rows": [
                        {"candidateId": "c1", "summary": "支持現案", "claimIds": ["c0"]},
                        {"candidateId": "c2", "summary": "反對現案", "claimIds": ["c1"]}]}]}
            elif stage == "verify":
                result = {"results": [{"questionId": payload["questions"][0]["id"], "summarySupported": True, "reason": "雙方直接原文",
                    "rows": [{"candidateId": "c1", "supported": True, "reason": ""}, {"candidateId": "c2", "supported": True, "reason": ""}]}]}
            else:
                self.fail("Unexpected request: " + stage)
            return {"result": result, "inputHash": stage, "model": "test-model", "requestedModel": "sky-quality", "generatedAt": "2026-11-16", "usage": {}}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(B, "WORK", Path(tmp)), mock.patch.object(B, "request", side_effect=fake_request):
            result = B.compare_topic("交通", [first, second], data)
        q = result["questions"][0]
        self.assertEqual(q["claimIds"], ["a1", "a2"])
        self.assertEqual(q["rows"][1]["claimIds"], ["a2"])
        self.assertTrue(q["summaryVerified"])

    def test_semantic_retry_is_bounded_and_keeps_original_evidence(self):
        data = fixture()
        q = next(t for t in data["topics"] if t["id"] == "housing")["questions"][0]
        q["summaryVerified"] = False
        q["rows"][0]["verified"] = False

        def fake_request(stage, instructions, payload, schema, max_output=16000):
            if stage == "semantic_repair":
                result = {"relation": "方向相近", "summary": "有條件提出社宅方案，目前缺其他可比資料。",
                          "rows": [{"candidateId": "c1", "summary": "提出一千戶社宅，以中央經費為前提。"}]}
            elif stage == "verify":
                self.assertEqual(payload["questions"][0]["relation"], "尚無法比較")
                result = {"results": [{"questionId": "housing-1", "summarySupported": True, "reason": "",
                          "rows": [{"candidateId": "c1", "supported": True, "reason": ""}]}]}
            else:
                self.fail(stage)
            return {"result": result, "inputHash": stage, "model": "test-model", "requestedModel": "sky-quality", "generatedAt": "2026-11-16", "usage": {}}

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(B, "WORK", Path(tmp)), mock.patch.object(B, "request", side_effect=fake_request) as request:
            B.repair_summaries(data, 1)
            B.repair_summaries(data, 1)
        self.assertEqual(request.call_count, 2)
        self.assertTrue(q["summaryVerified"])
        self.assertEqual(q["relation"], "尚無法比較")
        self.assertEqual(q["claimIds"], ["a1"])
        self.assertEqual(q["semanticRepairAttempt"], 1)

    def test_precomputing_briefs_cannot_publish_an_incomplete_snapshot(self):
        data = fixture()
        data["topics"] = [t for t in data["topics"] if t["id"] == "housing"]

        def fake_request(stage, instructions, payload, schema, max_output=16000):
            if stage == "topic_brief":
                result = {"findings": [{"text": "有條件的社宅方案。", "claimIds": ["c0"]}]}
            elif stage == "brief_verify":
                result = {"results": [{"index": 0, "supported": True, "reason": ""}]}
            else:
                self.fail(stage)
            return {"result": result, "inputHash": stage, "model": "test-model", "requestedModel": "sky-quality", "generatedAt": "2026-11-16", "usage": {}}

        with mock.patch.object(B, "request", side_effect=fake_request), mock.patch.object(B, "save") as save:
            result = B.add_topic_briefs(data, 1, finalize=False)
        save.assert_not_called()
        self.assertTrue(result["topics"][0]["briefFindings"][0]["verified"])


if __name__ == "__main__":
    unittest.main()
