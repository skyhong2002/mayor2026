#!/usr/bin/env python3
"""Merge roster + per-commission 號次 files into the published candidate list,
and reconcile every count against the official totals.

Inputs (all official):
  data/elections/2026/registered.csv        中選會 候選人登記名冊 (parse_roster.py)
  data/elections/2026/registered-seats.csv  中選會 政黨推薦登記彙總表（應選名額）
  data/elections/2026/numbers/<route>.csv   各選委會 號次公告 (numbers/<route>.py)
  state/elections/raw/vd2022/**             中選會選舉資料庫 2022 地方選舉 (incumbency + geography)

Outputs:
  data/elections/2026/candidates.csv        one row per candidate on the ballot (model.FIELDS)
  data/elections/2026/geography.json        county → township codes/names used for keys
  data/elections/2026/sources.json          every source URL with fetchedAt / sha256
  data/elections/2026/reconciliation.{json,md}

The reconciliation never drops a difference silently: every registrant without a
號次, every 號次 row without a registrant, every gap in 號次, every district whose
count exceeds its seats-independent sanity bounds, and every category whose total
disagrees with the CEC press releases is listed. Known, sourced explanations live
in data/elections/2026/explanations.csv (category,district,name,kind,source,note) and are
matched by (category, district, name).

    python3 scripts/elections/merge.py            # stdlib only; needs state/elections/raw/vd2022
"""

from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402
from model import (CANDIDATES_CSV, CATEGORIES, COUNTIES, COUNTY_NAME, COUNTY_ROUTE, DATA_DIR, FIELDS,  # noqa: E402
                   OFFICIAL_QUALIFIED, OFFICIAL_REGISTERED, OFFICIAL_SEATS, OFFICIAL_SOURCES, RECONCILIATION_JSON,
                   RECONCILIATION_MD, SOURCES_JSON)
from numbers_common import NUMBERS_DIR, norm_district, norm_name  # noqa: E402

VD2022 = fetch.STATE_DIR / "raw" / "vd2022"
VD2022_SOURCE = "https://data.cec.gov.tw/選舉資料庫/votedata.zip"
EXPLANATIONS = DATA_DIR / "explanations.csv"

# 2022 CEC DB folder → our category
VD_CATEGORY = {
    "C1/city": "county-mayor", "C1/prv": "municipal-mayor",
    "T1/city": "county-councilor", "T2/city": "county-councilor", "T3/city": "county-councilor",
    "T1/prv": "municipal-councilor", "T2/prv": "municipal-councilor", "T3/prv": "municipal-councilor",
    "D1": "township-mayor", "D2": "indigenous-district-chief",
    "R1": "township-rep", "R2": "township-rep", "R3": "indigenous-district-rep",
    "V1": "village-chief",
}
# In the CEC DB "city" means 縣市 and "prv" means 直轄市 for C1/T*.


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def strip_roman(name: str) -> str:
    """'宋雨蓁 Nikar．Falong' / '張宇廷YaguUtaw' → Han part only (matching key)."""
    han = re.sub(r"[A-Za-z\s．‧·・\-'’]+", "", name or "")
    return han or name


def name_keys(name: str) -> list[str]:
    n = norm_name(name)
    keys = [n, strip_roman(n)]
    return list(dict.fromkeys(k for k in keys if k))


# -- geography (from the 2022 CEC DB, names unchanged in 2026 unless re-zoned) ----

class Geo:
    def __init__(self, root: Path | None = None) -> None:
        root = root or VD2022
        self.towns: dict[str, dict[str, str]] = collections.defaultdict(dict)    # county slug → town name → code
        self.villages: dict[tuple[str, str], dict[str, str]] = collections.defaultdict(dict)  # (county, town) → village → code
        base = root / "V1" / "elbase.csv"
        if not base.exists():
            raise SystemExit(f"merge: {base} missing — download {VD2022_SOURCE} (see README) first")
        county_by_code: dict[tuple[str, str], str] = {}
        town_by_code: dict[tuple[str, str, str], str] = {}
        for folder in ("V1", "D1", "D2"):
            path = root / folder / "elbase.csv"
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig") as fh:
                for prv, city, _area, dept, li, name in csv.reader(fh):
                    name = name.strip()
                    if dept == "000" and li == "0000" and prv != "00":
                        slug = _county_slug(name)
                        if slug:
                            county_by_code[(prv, city)] = slug
                    elif li == "0000" and dept != "000":
                        slug = county_by_code.get((prv, city))
                        if slug:
                            self.towns[slug].setdefault(name, dept)
                            town_by_code[(prv, city, dept)] = name
                    elif li != "0000":
                        slug = county_by_code.get((prv, city))
                        town = town_by_code.get((prv, city, dept))
                        if slug and town:
                            self.villages[(slug, town)].setdefault(name, li)

    def split_town(self, county: str, rest: str) -> tuple[str, str]:
        """'東區南門里' → ('東區', '南門里') using the longest known township prefix."""
        for town in sorted(self.towns.get(county, {}), key=len, reverse=True):
            if rest.startswith(town):
                return town, rest[len(town):]
        m = re.match(r"(.+?[區鄉鎮市])(.*)$", rest)
        return (m.group(1), m.group(2)) if m else (rest, "")

    def town_code(self, county: str, town: str) -> str:
        code = self.towns.get(county, {}).get(town)
        return f"t{code}" if code else "t" + hashlib.sha1(town.encode()).hexdigest()[:6]

    def village_code(self, county: str, town: str, village: str) -> str:
        code = self.villages.get((county, town), {}).get(village)
        return f"v{code}" if code else "v" + hashlib.sha1(village.encode()).hexdigest()[:6]


def _county_slug(name: str) -> str | None:
    name = name.replace("台", "臺")
    for slug, cname, _ in COUNTIES:
        if cname == name:
            return slug
    return None


def split_district(geo: Geo, category: str, label: str) -> dict[str, str]:
    """Registered-style district label → county/township/district/village + key."""
    label = norm_district(label)
    county = next((slug for slug, cname, _ in COUNTIES if label.startswith(cname)), "")
    if not county:
        raise ValueError(f"no county in district label {label!r}")
    rest = label[len(COUNTY_NAME[county]):]
    level = CATEGORIES[category]["level"]
    out = {"county": county, "township": "", "district": "", "village": "", "districtKey": ""}
    if level == "county":
        m = re.match(r"第(\d+)選舉區$", rest)
        if m:
            out["district"] = f"第{m.group(1)}選舉區"
            out["districtKey"] = f"d{int(m.group(1)):02d}"
        elif rest:
            out["district"] = rest
            out["districtKey"] = "d-" + hashlib.sha1(rest.encode()).hexdigest()[:6]
        else:
            out["district"] = COUNTY_NAME[county]
            out["districtKey"] = "all"
        return out
    town, tail = geo.split_town(county, rest)
    out["township"] = town
    tkey = geo.town_code(county, town)
    if level == "township":
        m = re.match(r"第(\d+)選舉區$", tail)
        if m:
            out["district"] = f"第{m.group(1)}選舉區"
            out["districtKey"] = f"{tkey}-d{int(m.group(1)):02d}"
        else:
            out["district"] = town
            out["districtKey"] = tkey
        return out
    out["village"] = tail
    out["district"] = tail
    out["districtKey"] = f"{tkey}-{geo.village_code(county, town, tail)}"
    return out


# -- incumbency -----------------------------------------------------------------

def winners_2022(root: Path | None = None) -> set[tuple[str, ...]]:
    """Keys of 2022 winners: (category, county, scope, name-key)."""
    root = root or VD2022
    keys: set[tuple[str, ...]] = set()
    for folder, category in VD_CATEGORY.items():
        base_path = root / folder / "elbase.csv"
        cand_path = root / folder / "elcand.csv"
        if not cand_path.exists():
            continue
        names: dict[tuple[str, ...], str] = {}
        with base_path.open(encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                prv, city, area, dept, li, name = row[:6]
                names[(prv, city, area, dept, li)] = name.strip()
                names.setdefault((prv, city, "00", dept, li), name.strip())
        with cand_path.open(encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                prv, city, area, dept, li = row[:5]
                name, elected = row[6], row[14].strip()
                if elected != "*":
                    continue
                county = _county_slug(names.get((prv, city, "00", "000", "0000"), ""))
                if not county:
                    continue
                town = names.get((prv, city, "00", dept, "0000"), "") if dept != "000" else ""
                village = names.get((prv, city, "00", dept, li), "") if li != "0000" else ""
                level = CATEGORIES[category]["level"]
                scope = "" if level == "county" else town if level == "township" else f"{town}/{village}"
                for key in name_keys(name):
                    keys.add((category, county, scope, key))
    return keys


def incumbent_scope(row: dict[str, str]) -> str:
    level = CATEGORIES[row["category"]]["level"]
    return "" if level == "county" else row["township"] if level == "township" else f"{row['township']}/{row['village']}"


# -- merge ----------------------------------------------------------------------

def main() -> int:
    geo = Geo()
    registered = read_csv(DATA_DIR / "registered.csv")
    seats_rows = read_csv(DATA_DIR / "registered-seats.csv")
    explanations = {(e["category"], norm_district(e["district"]), norm_name(e["name"])): e
                    for path in sorted(DATA_DIR.glob("explanations*.csv")) for e in read_csv(path)}
    winners = winners_2022()

    reg_index: dict[tuple[str, str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for r in registered:
        for key in name_keys(r["name"]):
            reg_index[(r["category"], norm_district(r["district"]), key)].append(r)

    numbered: list[dict[str, str]] = []
    missing_routes = []
    for slug, cname, route in COUNTIES:
        rows = read_csv(NUMBERS_DIR / f"{route}.csv")
        if not rows:
            missing_routes.append(route)
        for row in rows:
            row["_route"] = route
            numbered.append(row)

    # Manual layer (data/elections/2026/manual.csv): official rows the parsers cannot
    # read as text (造字、圖片姓名). Every row cites the official publication.
    manual = read_csv(DATA_DIR / "manual.csv")
    route_of = {cname: route for _, cname, route in COUNTIES}
    for m in manual:
        key = (m["category"], norm_district(m["district"]), str(int(m["number"])))
        if m["action"] == "rename":
            hit = [r for r in numbered if (r["category"], norm_district(r["district"]), str(int(r["number"]))) == key]
            if len(hit) != 1:
                raise SystemExit(f"manual.csv rename matches {len(hit)} rows: {m}")
            hit[0].update(name=m["name"], note=m["note"])
        elif m["action"] == "add":
            if any((r["category"], norm_district(r["district"]), str(int(r["number"]))) == key for r in numbered):
                raise SystemExit(f"manual.csv add duplicates an existing row: {m}")
            route = next(r for c, r in route_of.items() if m["district"].startswith(c))
            numbered.append({**m, "_route": route, "fetchedAt": "", "_manual": "1"})

    out_rows: list[dict[str, str]] = []
    matched_reg: set[int] = set()
    not_registered: list[dict[str, str]] = []
    rec_of: dict[int, dict[str, str]] = {}
    for row in numbered:
        cat = row["category"]
        district = norm_district(row["district"])
        reg = None
        for key in name_keys(row["name"]):
            for cand in reg_index.get((cat, district, key), []):
                if id(cand) not in matched_reg:
                    reg = cand
                    break
            if reg:
                break
        if reg:
            matched_reg.add(id(reg))
        else:
            not_registered.append(row)
        geo_parts = split_district(geo, cat, district)
        party = row.get("party") or (reg or {}).get("party") or ""
        rec = {
            "category": cat, **geo_parts, "number": row["number"], "name": row["name"],
            "gender": row.get("gender", ""), "birthYear": row.get("birthYear", ""), "party": party,
            "numberSource": row.get("sourceFile") or row["source"], "numberFetchedAt": row.get("fetchedAt", ""),
            "rosterSource": OFFICIAL_SOURCES["roster"] if reg else "",
            "profileSource": row["source"] if row.get("gender") or row.get("birthYear") else "",
        }
        rec["incumbent"] = "Y" if any((cat, rec["county"], incumbent_scope(rec), k) in winners for k in name_keys(rec["name"])) else ""
        rec["id"] = f"{rec['county']}-{cat}-{rec['districtKey']}-{int(rec['number']):02d}"
        out_rows.append(rec)
        rec_of[id(row)] = rec

    # Same person, different spelling (異體字、造字、原住民族名拼寫): pair a ballot row with
    # a registrant only when an explanation documents the variant and the district has
    # exactly one unmatched entry on each side.
    variants = {(c, d) for (c, d, _n), e in explanations.items() if e.get("kind") == "name-variant"}
    unmatched_reg: dict[tuple[str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for r in registered:
        if id(r) not in matched_reg:
            unmatched_reg[(r["category"], norm_district(r["district"]))].append(r)
    pending: dict[tuple[str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for row in not_registered:
        pending[(row["category"], norm_district(row["district"]))].append(row)
    paired = 0
    for key, rows_ in pending.items():
        regs = unmatched_reg.get(key, [])
        blank = [r for r in regs if not r["name"].strip()]
        if len(regs) > 1 and len(blank) == 1:
            regs = blank  # the roster left the name blank (造字); the others are genuinely absent
        if key in variants and len(rows_) == 1 and len(regs) == 1:
            matched_reg.add(id(regs[0]))
            not_registered.remove(rows_[0])
            rec = rec_of[id(rows_[0])]
            rec["party"] = rec["party"] or regs[0].get("party", "")
            rec["rosterSource"] = OFFICIAL_SOURCES["roster"]
            paired += 1

    order = {c: i for i, c in enumerate(CATEGORIES)}
    county_order = {slug: i for i, (slug, _, _) in enumerate(COUNTIES)}
    out_rows.sort(key=lambda r: (county_order[r["county"]], order[r["category"]], r["township"], r["districtKey"], int(r["number"])))
    ids = collections.Counter(r["id"] for r in out_rows)
    dup_ids = [i for i, n in ids.items() if n > 1]

    with CANDIDATES_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(out_rows)

    # -- reconciliation ----------------------------------------------------------
    numbered_routes = {r["_route"] for r in numbered}
    covered_counties = {slug for slug, _, route in COUNTIES if route in numbered_routes}
    not_numbered = [r for r in registered if id(r) not in matched_reg]
    # A (county, category) with no 號次 rows at all means its publication has not
    # been parsed yet — that is "pending source", not an unexplained difference.
    covered_pairs = {(r["county"], r["category"]) for r in out_rows}

    def explain(cat: str, district: str, name: str) -> dict[str, str] | None:
        for key in name_keys(name):
            hit = explanations.get((cat, norm_district(district), key))
            if hit:
                return hit
        return None

    issues: list[dict[str, Any]] = []
    for r in not_numbered:
        county = next((slug for slug, cname, _ in COUNTIES if r["district"].startswith(cname)), "")
        exp = explain(r["category"], r["district"], r["name"])
        issues.append({
            "kind": "registered-without-number", "category": r["category"], "county": county,
            "district": r["district"], "name": r["name"],
            "status": ("pending-source" if (exp or {}).get("kind") == "pending" else "explained") if exp
                      else ("pending-source" if (county, r["category"]) not in covered_pairs else "unexplained"),
            "explanation": (exp or {}).get("kind", ""), "evidence": (exp or {}).get("source", ""), "note": (exp or {}).get("note", ""),
        })
    for r in not_registered:
        exp = explain(r["category"], r["district"], r["name"])
        issues.append({
            "kind": "numbered-not-in-roster", "category": r["category"], "county": split_district(geo, r["category"], r["district"])["county"],
            "district": r["district"], "name": r["name"], "number": r["number"],
            "status": "explained" if exp else "unexplained",
            "explanation": (exp or {}).get("kind", ""), "evidence": (exp or {}).get("source", "") or r.get("source", ""), "note": (exp or {}).get("note", ""),
        })
    by_district: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    for r in out_rows:
        by_district[(r["category"], r["county"] + "|" + r["districtKey"])].append(int(r["number"]))
    for (cat, key), nums in sorted(by_district.items()):
        if sorted(nums) != list(range(1, len(nums) + 1)):
            issues.append({"kind": "number-sequence", "category": cat, "county": key.split("|")[0], "district": key,
                           "numbers": sorted(nums), "status": "unexplained"})
    for i in dup_ids:
        issues.append({"kind": "duplicate-id", "id": i, "status": "unexplained"})

    # seats (only the four categories with official per-district seat tables)
    seats = {(s["category"], norm_district(s["district"])): int(s["seats"]) for s in seats_rows if s["district"] != "總計"}
    district_counts: dict[tuple[str, str], int] = collections.Counter()
    for r in numbered:
        district_counts[(r["category"], norm_district(r["district"]))] += 1
    for (cat, district), n_seats in sorted(seats.items()):
        n = district_counts.get((cat, district), 0)
        county = next((slug for slug, cname, _ in COUNTIES if district.startswith(cname)), "")
        if county in covered_counties and n == 0:
            issues.append({"kind": "district-without-candidates", "category": cat, "county": county, "district": district,
                           "seats": n_seats, "status": "unexplained"})

    totals = {}
    for cat in CATEGORIES:
        totals[cat] = {
            "label": CATEGORIES[cat]["label"],
            "officialRegistered": OFFICIAL_REGISTERED[cat],
            "rosterRegistered": sum(1 for r in registered if r["category"] == cat),
            "officialQualified": OFFICIAL_QUALIFIED.get(cat),
            "officialSeats": OFFICIAL_SEATS[cat],
            "rosterSeats": sum(v for (c, _), v in seats.items() if c == cat) or None,
            "onBallot": sum(1 for r in out_rows if r["category"] == cat),
            "withdrawnOrDisqualified": sum(1 for i in issues if i["kind"] == "registered-without-number" and i["category"] == cat and i["status"] == "explained"),
            "unexplained": sum(1 for i in issues if i.get("category") == cat and i["status"] == "unexplained"),
            "pendingSource": sum(1 for i in issues if i.get("category") == cat and i["status"] == "pending-source"),
        }
    for cat, t in totals.items():
        if t["rosterRegistered"] != t["officialRegistered"]:
            issues.append({"kind": "roster-total", "category": cat, "status": "unexplained",
                           "note": f"名冊 {t['rosterRegistered']} ≠ 新聞稿 {t['officialRegistered']}"})
        if t["officialQualified"] is not None and not t["pendingSource"]:
            # every qualified candidate should be on the ballot unless they withdrew after 審定
            expected = t["officialQualified"]
            if t["onBallot"] != expected:
                issues.append({"kind": "qualified-total", "category": cat,
                               "status": "explained" if t["onBallot"] + t["withdrawnOrDisqualified"] >= expected and not t["unexplained"] else "unexplained",
                               "note": f"號次 {t['onBallot']} vs 中選會審定 {expected}"})

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    report = {
        "generatedAt": now,
        "coverage": {"counties": len(covered_counties), "missingRoutes": missing_routes},
        "totals": totals,
        "issues": issues,
        "sources": OFFICIAL_SOURCES,
    }
    RECONCILIATION_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    RECONCILIATION_MD.write_text(render_md(report), encoding="utf-8")
    write_sources(numbered, now)
    print(f"merge: {len(out_rows)} candidates on ballot from {len(covered_counties)}/22 commissions; "
          f"{sum(1 for i in issues if i['status'] == 'unexplained')} unexplained, "
          f"{sum(1 for i in issues if i['status'] == 'pending-source')} pending-source")
    for cat, t in totals.items():
        print(f"  {t['label']}: 登記 {t['rosterRegistered']}/{t['officialRegistered']} 審定 {t['officialQualified']} "
              f"號次 {t['onBallot']} 應選 {t['officialSeats']} 未解釋 {t['unexplained']} 待來源 {t['pendingSource']}")
    return 0


def write_sources(numbered: list[dict[str, str]], now: str) -> None:
    urls: dict[str, dict[str, Any]] = {}
    for row in numbered:
        for key in ("source", "sourceFile"):
            url = row.get(key)
            if url and url not in urls:
                urls[url] = {"url": url, "route": row["_route"], "kind": "ballot-numbers", "fetchedAt": row.get("fetchedAt", "")}
    for kind, url in OFFICIAL_SOURCES.items():
        urls.setdefault(url, {"url": url, "route": "central", "kind": kind})
    urls.setdefault(VD2022_SOURCE, {"url": VD2022_SOURCE, "route": "central", "kind": "2022-results (incumbency)"})
    for entry in urls.values():
        api = entry["url"]
        m = re.match(r"https://web\.cec\.gov\.tw/([a-z]+)/article/(\d+)$", api)
        if m:
            api = f"{fetch.BASE}/api/{m.group(1)}/article/{m.group(2)}"
        meta = fetch.meta(api)
        if meta:
            entry["fetchedAt"] = entry.get("fetchedAt") or meta.get("fetchedAt", "")
            entry["sha256"] = meta.get("sha256", "")
    SOURCES_JSON.write_text(json.dumps({"generatedAt": now, "sources": sorted(urls.values(), key=lambda e: (e["route"], e["url"]))},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def render_md(report: dict[str, Any]) -> str:
    lines = ["# 2026 地方選舉候選人名單對帳報告", "",
             f"產生時間（UTC）：{report['generatedAt']}　涵蓋選委會：{report['coverage']['counties']}/22"
             + (f"（缺：{', '.join(report['coverage']['missingRoutes'])}）" if report['coverage']['missingRoutes'] else ""), "",
             "官方總數來源：[登記人數與應選名額](%s)、[登記名冊](%s)、[中選會審定](%s)。" % (
                 OFFICIAL_SOURCES["registered"], OFFICIAL_SOURCES["roster"], OFFICIAL_SOURCES["qualified"]), "",
             "| 類別 | 登記（新聞稿） | 登記（名冊） | 中選會審定 | 有號次 | 應選名額 | 已解釋未列入 | 未解釋 | 待來源 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for t in report["totals"].values():
        lines.append(f"| {t['label']} | {t['officialRegistered']} | {t['rosterRegistered']} | {t['officialQualified'] if t['officialQualified'] is not None else '—'} "
                     f"| {t['onBallot']} | {t['officialSeats']} | {t['withdrawnOrDisqualified']} | {t['unexplained']} | {t['pendingSource']} |")
    lines += ["", "「已解釋未列入」＝登記但無號次，且有官方公告佐證（撤回登記、審定不合格等）；",
              "「待來源」＝該選委會的號次公告尚未取得；「未解釋」需要人工追查，不會被靜默略過。", ""]
    kinds = {"registered-without-number": "登記名冊有、號次公告無", "numbered-not-in-roster": "號次公告有、登記名冊無",
             "number-sequence": "號次不連續或重複", "duplicate-id": "ID 重複", "district-without-candidates": "選舉區無候選人",
             "roster-total": "名冊總數不符", "qualified-total": "與中選會審定人數不符"}
    for status, title in (("unexplained", "未解釋的差異"), ("explained", "已解釋的差異"), ("pending-source", "待取得號次來源")):
        rows = [i for i in report["issues"] if i["status"] == status]
        lines += [f"## {title}（{len(rows)}）", ""]
        if not rows:
            lines += ["無。", ""]
            continue
        if status == "pending-source":
            per = collections.Counter((i["county"], i["category"]) for i in rows)
            for (county, cat), n in sorted(per.items()):
                lines.append(f"- {COUNTY_NAME.get(county, county)} {CATEGORIES[cat]['label']}：{n} 人")
            lines.append("")
            continue
        lines += ["| 類型 | 類別 | 選舉區 | 姓名／內容 | 說明 | 佐證 |", "|---|---|---|---|---|---|"]
        for i in rows:
            cat = CATEGORIES.get(i.get("category", ""), {}).get("label", "")
            what = i.get("name") or i.get("note") or (" ".join(map(str, i.get("numbers", []))) if i.get("numbers") else i.get("id", ""))
            lines.append(f"| {kinds.get(i['kind'], i['kind'])} | {cat} | {i.get('district', '')} | {what} "
                         f"| {i.get('explanation', '')} {i.get('note', '') if i.get('name') else ''} | {i.get('evidence', '')} |")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
