from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from home_fixture import HomeData, build_fixture, home


class HomeParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = 0
        self.columns = {}
        self.current = None
        self.boot = ""
        self.in_boot = False
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        self.nodes += 1
        attrs = dict(attributes)
        if tag == "section" and "feed-col" in attrs.get("class", "").split():
            self.current = attrs["data-col"]
            self.columns[self.current] = []
        if tag == "article" and "feed-post" in attrs.get("class", "").split():
            self.columns[self.current].append(attrs["data-id"])
        if tag == "script" and attrs.get("id") == "home-boot":
            self.in_boot = True

    def handle_endtag(self, tag):
        if tag == "section":
            self.current = None
        if tag == "script":
            self.in_boot = False

    def handle_data(self, value):
        if self.in_boot:
            self.boot += value


class HomepageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.data = HomeData()

    def render(self):
        return build_fixture(self.root, self.data).read_text()

    def test_initial_cards_are_bounded_and_more_data_is_preserved(self):
        html = self.render()
        parsed = HomeParser(html)
        self.assertEqual(set(parsed.columns), {"all", *["city:" + city for city in home.S.CITY_ORDER]})
        self.assertEqual([len(ids) for ids in parsed.columns.values()], [10] * 7)
        self.assertEqual(json.loads(parsed.boot)["perCol"], 10)
        self.assertEqual(html.count('data-act="more"'), 7)
        self.assertIn("<noscript>", html)
        self.assertIn('href="/source/"', html)
        self.assertIn('href="/?candidate=taipei-fixture"', html)
        bundle = json.loads((self.root / "data/feed/all.json").read_text())
        self.assertEqual(bundle["total"], 450)
        self.assertEqual(bundle["count"], 400)
        self.assertEqual(bundle["posts"][:10], [home._slim(post) for post in self.data.all_posts()[:10]])
        for city in home.S.CITY_ORDER:
            bundle = json.loads((self.root / f"data/feed/{city}.json").read_text())
            self.assertEqual(bundle["count"], 75)
            self.assertEqual(parsed.columns["city:" + city], [post["id"] for post in bundle["posts"][:10]])
            candidate = json.loads((self.root / f"data/feed/c/{city}-fixture.json").read_text())
            self.assertEqual(candidate["posts"], bundle["posts"])

    def test_html_and_dom_budget_reduction_on_same_snapshot(self):
        with mock.patch.object(home, "SSR_PER_COL", 30):
            previous = self.render()
        current = self.render()
        self.assertLess(len(current.encode()), len(previous.encode()) * 0.5)
        self.assertLess(HomeParser(current).nodes, HomeParser(previous).nodes * 0.5)

    def test_small_and_empty_columns_remain_usable_without_javascript(self):
        self.data = HomeData(per_city=4)
        html = self.render()
        parsed = HomeParser(html)
        self.assertEqual(len(parsed.columns["city:taipei"]), 4)
        self.assertNotIn('data-act="more"', home.column("test", "test", "content", total=4))
        self.assertEqual(len(parsed.columns["all"]), 10)
        self.data = HomeData(per_city=0)
        html = self.render()
        self.assertIn("這個城市尚無貼文", html)
        self.assertNotIn('data-act="more"', html)
        self.assertIn('href="/source/"', html)


if __name__ == "__main__":
    unittest.main()
