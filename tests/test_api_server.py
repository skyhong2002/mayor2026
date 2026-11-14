import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import api_server  # noqa: E402


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def post(i: int, cand: str, platform: str = "facebook", topics=("交通",), day: int = 1) -> dict:
    return {"id": f"{platform}:{cand}:{i}", "candidateId": cand, "platform": platform,
            "postedAt": f"2026-11-{day:02d}T0{i % 10}:00:00+00:00", "text": f"post {i} 捷運",
            "topics": list(topics), "postingIntent": {"type": "self_initiated"}, "url": f"https://example.com/{i}"}


class ApiServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        release = Path(cls.tmp.name) / "releases" / "r1"
        current = Path(cls.tmp.name) / "current"
        a = [post(i, "alice", day=10 - i) for i in range(5)]
        b = [post(i + 10, "bob", platform="threads", topics=("住宅",), day=9 - i) for i in range(3)]
        write(release / "api" / "candidates.json", {"version": 1, "count": 2, "candidates": [
            {"id": "alice", "city": "taipei", "name": "乙"}, {"id": "bob", "city": "tainan"}]})
        write(release / "api" / "posts" / "alice.json", {"version": 1, "count": 5, "candidate": {"id": "alice"}, "posts": a})
        write(release / "api" / "posts" / "bob.json", {"version": 1, "count": 3, "candidate": {"id": "bob"}, "posts": b})
        write(release / "api" / "latest.json", {"version": 1, "count": 8, "posts": (a + b)})
        write(release / "api" / "policy-match.json", {"version": 1, "questions": []})
        write(release / "api" / "elections" / "2026" / "index.json", {
            "schemaVersion": 1, "generatedAt": "2026-11-12T00:00:00+00:00", "electionDay": "2026-11-28",
            "counties": [{"id": "taipei", "label": "臺北市"}],
            "categories": [{"id": "municipal-mayor", "label": "直轄市長"}]})
        write(release / "api" / "elections" / "2026" / "taipei.json", {"categories": []})
        (release / "api" / "elections" / "2026" / "candidates.csv").write_text(
            "id,category,county,township,district,districtKey,village,number,name,gender,birthYear,party,incumbent\n"
            "t-1,municipal-mayor,taipei,,臺北市,all,,2,乙,,,甲黨,Y\n"
            "t-2,municipal-mayor,taipei,,臺北市,all,,1,丙,,1970,乙黨,\n", encoding="utf-8")
        current.symlink_to(release)
        cls.server = api_server.make_server(current, "127.0.0.1", 0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path: str):
        try:
            with urllib.request.urlopen(self.base + path) as res:
                return res.status, json.loads(res.read()), res.headers
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read()), exc.headers

    def test_limit_and_offset_keep_shape(self):
        status, body, headers = self.get("/api/latest.json?limit=3&offset=2")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual((body["count"], body["total"], body["offset"], body["limit"]), (3, 8, 2, 3))
        self.assertEqual(len(body["posts"]), 3)
        self.assertEqual(body["version"], 1)
        self.assertIn("offset=5", body["next"])

    def test_post_filters_and_fields(self):
        _, body, _ = self.get("/api/posts.json?city=tainan&fields=id,platform")
        self.assertEqual(body["total"], 3)
        self.assertEqual(set(body["posts"][0]), {"id", "platform"})
        _, body, _ = self.get("/api/posts.json?topic=%E4%BA%A4%E9%80%9A&since=2026-11-08&limit=1")
        self.assertEqual(body["total"], 3)  # alice days 10, 9, 8
        self.assertEqual(body["posts"][0]["postedAt"][:10], "2026-11-10")
        _, body, _ = self.get("/api/posts/bob.json?platform=threads&limit=1")
        self.assertEqual(body["candidate"], {"id": "bob"})
        self.assertEqual(body["total"], 3)

    def test_all_posts_sorted_newest_first(self):
        _, body, _ = self.get("/api/posts.json?limit=100")
        stamps = [p["postedAt"] for p in body["posts"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        self.assertIsNone(body["next"])

    def test_election_candidates(self):
        _, body, _ = self.get("/api/elections/2026/candidates.json?county=%E8%87%BA%E5%8C%97%E5%B8%82&sort=number")
        self.assertEqual([c["number"] for c in body["candidates"]], [1, 2])
        self.assertEqual(body["candidates"][0]["countyLabel"], "臺北市")
        _, body, _ = self.get("/api/elections/2026/candidates.json?incumbent=true")
        self.assertEqual([c["name"] for c in body["candidates"]], ["乙"])
        self.assertEqual(body["candidates"][0]["trackedFeed"], "/taipei/alice/")

    def test_errors(self):
        self.assertEqual(self.get("/api/latest.json?limit=-1")[0], 400)
        self.assertEqual(self.get("/api/latest.json?county=x")[0], 400)
        self.assertEqual(self.get("/api/policy-match.json?limit=1")[0], 400)
        self.assertEqual(self.get("/api/elections/2026/taipei.json?limit=1")[0], 400)
        self.assertEqual(self.get("/api/missing.json?limit=1")[0], 404)
        self.assertEqual(self.get("/api/../secret.json")[0], 404)

    def test_unknown_params_ignored(self):
        status, body, _ = self.get("/api/policy-match.json?v=123")
        self.assertEqual((status, body), (200, {"version": 1, "questions": []}))


if __name__ == "__main__":
    unittest.main()
