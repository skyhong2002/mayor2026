import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import generate_seo_pages
import validate_public_outputs

BASE = "https://mayor2026.observe.tw"
CANDIDATES = [
    {"id": "cand-a", "city": "taipei", "latestPostAt": "2026-10-22T16:28:38+00:00"},
    {"id": "cand-b", "city": "tainan", "latestPostAt": "2026-07-05T06:18:46.000Z"},
    {"id": "cand-c", "city": "kaohsiung"},
]


class SitemapEntriesTest(unittest.TestCase):
    def setUp(self):
        self.entries = dict(generate_seo_pages.sitemap_entries(CANDIDATES))

    def test_noindex_status_page_is_not_listed(self):
        self.assertNotIn("/status/", self.entries)

    def test_candidate_pages_use_their_latest_post_time(self):
        self.assertEqual(self.entries["/taipei/cand-a/"], "2026-10-22T16:28:38Z")
        self.assertEqual(self.entries["/source/cand-a/"], "2026-10-22T16:28:38Z")
        self.assertEqual(self.entries["/tainan/cand-b/"], "2026-07-05T06:18:46Z")
        self.assertIsNone(self.entries["/kaohsiung/cand-c/"])

    def test_feed_pages_use_newest_post_and_static_pages_omit_lastmod(self):
        self.assertEqual(self.entries["/"], "2026-10-22T16:28:38Z")
        self.assertEqual(self.entries["/spectrum/transport/"], "2026-10-22T16:28:38Z")
        self.assertIsNone(self.entries["/about/"])

    def test_render_omits_missing_lastmod(self):
        xml = generate_seo_pages.render_sitemap([("/about/", None), ("/", "2026-10-22T16:28:38Z")])
        self.assertIn(f"<url><loc>{BASE}/about/</loc></url>", xml)
        self.assertIn(f"<url><loc>{BASE}/</loc><lastmod>2026-10-22T16:28:38Z</lastmod></url>", xml)


class SitemapValidationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = mock.patch.object(validate_public_outputs, "SITE_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def page(self, path, canonical=None, noindex=False):
        target = self.root / path.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        robots = '<meta name="robots" content="noindex,follow">' if noindex else ""
        target.write_text(f'<link rel="canonical" href="{canonical or BASE + path}">{robots}', encoding="utf-8")

    def validate(self, *paths):
        urls = "".join(f"<url><loc>{BASE}{path}</loc></url>" for path in paths)
        (self.root / "sitemap.xml").write_text(
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
        errors: list[str] = []
        validate_public_outputs.validate_sitemap(errors)
        return errors

    def test_indexable_self_canonical_pages_pass(self):
        self.page("/")
        self.page("/source/cand-a/")
        self.assertEqual(self.validate("/", "/source/cand-a/"), [])

    def test_noindex_page_fails(self):
        self.page("/status/", noindex=True)
        self.assertEqual(self.validate("/status/"), [f"sitemap URL {BASE}/status/ is marked noindex"])

    def test_missing_page_and_foreign_canonical_fail(self):
        self.page("/spectrum/topic/transport/", canonical=f"{BASE}/spectrum/transport/")
        errors = self.validate("/nope/", "/spectrum/topic/transport/", "/nope/")
        self.assertIn(f"sitemap URL {BASE}/nope/ has no generated page", errors)
        self.assertIn(f"sitemap URL {BASE}/spectrum/topic/transport/ has canonical {BASE}/spectrum/transport/", errors)
        self.assertIn(f"sitemap.xml lists {BASE}/nope/ twice", errors)


if __name__ == "__main__":
    unittest.main()
