"""2026 local-election candidate dataset: helpers, merge logic, committed data integrity."""

from __future__ import annotations

import collections
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "elections"))

import merge  # noqa: E402
import model  # noqa: E402
import numbers_common as nc  # noqa: E402


def write(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)


class HelperTests(unittest.TestCase):
    def test_cn_number(self) -> None:
        self.assertEqual(nc.cn_number("十二"), 12)
        self.assertEqual(nc.cn_number("二十一"), 21)
        self.assertEqual(nc.cn_number("１３"), 13)
        self.assertEqual(nc.cn_number("十"), 10)

    def test_norm_district(self) -> None:
        self.assertEqual(nc.norm_district("台北市第十二選舉區"), "臺北市第12選舉區")
        self.assertEqual(nc.norm_district("南投縣中寮鄉 第１選舉區"), "南投縣中寮鄉第1選舉區")

    def test_name_keys_strip_romanization(self) -> None:
        self.assertIn("張宇廷", merge.name_keys("張宇廷YaguUtaw"))
        self.assertIn("宋雨蓁", merge.name_keys("宋雨蓁 Nikar．Falong"))
        self.assertEqual(merge.name_keys("王 小明"), ["王小明"])

    def test_party_slug(self) -> None:
        self.assertEqual(model.party_slug("民主進步黨"), "dpp")
        self.assertEqual(model.party_slug("中國國民黨"), "kmt")
        self.assertEqual(model.party_slug("無"), "none")


class GeoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        write(root / "V1" / "elbase.csv", [
            ["00", "000", "00", "000", "0000", "全國"],
            ["10", "018", "00", "000", "0000", "新竹市"],
            ["10", "018", "00", "010", "0000", "東區"],
            ["10", "018", "00", "010", "0001", "南門里"],
            ["68", "000", "00", "000", "0000", "桃園市"],
            ["68", "000", "00", "080", "0000", "平鎮區"],
            ["68", "000", "00", "080", "0003", "鎮興里"],
        ])
        write(root / "V1" / "elcand.csv", [
            ["10", "018", "00", "010", "0001", "1", "黃志成", "999", "1", "0500101", "71", "臺灣省", "大學", "Y", "*", " "],
            ["10", "018", "00", "010", "0001", "2", "落選人", "999", "1", "0500101", "71", "臺灣省", "大學", "N", " ", " "],
        ])
        self.root = root
        self.geo = merge.Geo(root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_village_split_uses_known_townships(self) -> None:
        # 平鎮區 contains 鎮: a naive regex would split after 平鎮.
        parts = merge.split_district(self.geo, "village-chief", "桃園市平鎮區鎮興里")
        self.assertEqual((parts["county"], parts["township"], parts["village"]), ("taoyuan", "平鎮區", "鎮興里"))
        self.assertEqual(parts["districtKey"], "t080-v0003")

    def test_council_and_mayor_keys(self) -> None:
        self.assertEqual(merge.split_district(self.geo, "county-councilor", "新竹市第3選舉區")["districtKey"], "d03")
        self.assertEqual(merge.split_district(self.geo, "county-mayor", "新竹市")["districtKey"], "all")

    def test_township_rep_key(self) -> None:
        parts = merge.split_district(self.geo, "township-rep", "新竹市東區第2選舉區")
        self.assertEqual((parts["township"], parts["districtKey"]), ("東區", "t010-d02"))

    def test_incumbent_only_for_winner_in_same_village(self) -> None:
        winners = merge.winners_2022(self.root)
        self.assertIn(("village-chief", "hsinchu-city", "東區/南門里", "黃志成"), winners)
        self.assertNotIn(("village-chief", "hsinchu-city", "東區/南門里", "落選人"), winners)


class CheckTests(unittest.TestCase):
    def test_check_reports_gaps_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            write(data / "registered.csv", [
                ["category", "district", "registeredOn", "name", "party", "note", "page", "source"],
                ["village-chief", "新竹市東區南門里", "115/09/01", "甲", "無", "", "1", "x"],
                ["village-chief", "新竹市東區南門里", "115/09/01", "乙", "無", "", "1", "x"],
                ["village-chief", "新竹市東區南門里", "115/09/01", "丙", "無", "", "1", "x"],
            ])
            write(data / "numbers" / "hcec.csv", [
                nc.NUMBER_FIELDS,
                ["village-chief", "新竹市東區南門里", "1", "甲", "", "", "", "u", "", "", ""],
                ["village-chief", "新竹市東區南門里", "3", "乙", "", "", "", "u", "", "", ""],
            ])
            with mock.patch.object(nc, "DATA_DIR", data), mock.patch.object(nc, "NUMBERS_DIR", data / "numbers"):
                report = nc.check("hcec", verbose=False)
        entry = report["categories"]["village-chief"]
        self.assertEqual(entry["notNumbered"], ["新竹市東區南門里 丙"])
        self.assertTrue(entry["problems"])


class CommittedDataTests(unittest.TestCase):
    """Integrity of the committed, published dataset (runs in CI without network)."""

    @classmethod
    def setUpClass(cls) -> None:
        if not model.CANDIDATES_CSV.exists():
            raise unittest.SkipTest("candidates.csv not generated yet")
        with model.CANDIDATES_CSV.open(encoding="utf-8") as fh:
            cls.rows = list(csv.DictReader(fh))

    def test_schema_and_vocabulary(self) -> None:
        counties = {slug for slug, _, _ in model.COUNTIES}
        for row in self.rows:
            self.assertEqual(list(row), model.FIELDS)
            self.assertIn(row["category"], model.CATEGORIES)
            self.assertIn(row["county"], counties)
            self.assertTrue(row["name"])
            self.assertTrue(row["numberSource"].startswith("https://web.cec.gov.tw/"), row["id"])
            self.assertIn(row["incumbent"], ("", "Y"))
            self.assertIn(row["gender"], ("", "男", "女"))

    def test_ids_unique_and_numbers_contiguous(self) -> None:
        ids = collections.Counter(r["id"] for r in self.rows)
        self.assertEqual([i for i, n in ids.items() if n > 1], [])
        per = collections.defaultdict(list)
        for r in self.rows:
            per[(r["county"], r["category"], r["districtKey"])].append(int(r["number"]))
        report = json.loads(model.RECONCILIATION_JSON.read_text(encoding="utf-8"))
        reported = {i["district"] for i in report["issues"] if i["kind"] == "number-sequence"}
        bad = {k: sorted(v) for k, v in per.items()
               if sorted(v) != list(range(1, len(v) + 1)) and f"{k[0]}|{k[2]}" not in reported}
        self.assertEqual(bad, {})

    def test_reconciliation_has_no_unexplained_total_mismatch(self) -> None:
        report = json.loads(model.RECONCILIATION_JSON.read_text(encoding="utf-8"))
        for cat, totals in report["totals"].items():
            self.assertEqual(totals["rosterRegistered"], totals["officialRegistered"], cat)
            self.assertLessEqual(totals["onBallot"], totals["officialRegistered"] + 50, cat)


if __name__ == "__main__":
    unittest.main()
