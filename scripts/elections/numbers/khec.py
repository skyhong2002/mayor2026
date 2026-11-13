#!/usr/bin/env python3
"""高雄市選舉委員會 → data/elections/2026/numbers/khec.csv

* 65530 高雄市第5屆里長選舉候選人姓名號次抽定一覽表 (PDF with text layer; table
  columns 選舉區 / 姓名 / 抽籤號次), published 2026-10-27.

NOT parsed (no machine-readable text, image-only scans; not OCR'd on purpose):
* 65370 高雄市第5屆市長、市議員選舉候選人姓名號次抽定一覽表
  https://web.cec.gov.tw/api/file/9bd4f559-e527-4f55-a4ef-21653d340f79.pdf (KONICA MINOLTA scan)
* 65760 公告高雄市第5屆市長選舉候選人名單…
  https://web.cec.gov.tw/api/file/b18b321c-76a2-43af-aae7-e985402e7300.pdf (image only)
* 直轄市山地原住民區長 / 區民代表 (桃源、那瑪夏、茂林): no 號次 publication found on khec.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/khec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "khec"
COUNTY = "高雄市"


def cell(value: str | None) -> str:
    return re.sub(r"\s*\n\s*", "", (value or "")).strip()


def village_rows() -> list[dict]:
    import pdfplumber

    art = fetch.article(ROUTE, "65530")
    url = fetch.article_url(ROUTE, "65530")
    rows = []
    for file_name in art["files"]:
        if not file_name.endswith(".pdf"):
            continue
        file_url = fetch.file_url(file_name)
        fetched = fetch.meta(file_url).get("fetchedAt", "")
        with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    for raw in table:
                        vals = [cell(v) for v in raw] + [""] * 3
                        district, name, num = vals[:3]
                        if not district.startswith(COUNTY) or not num.isdigit():
                            continue
                        rows.append({"category": "village-chief", "district": district, "number": num, "name": name,
                                     "source": url, "sourceFile": file_url, "fetchedAt": fetched})
    if not rows:
        raise SystemExit(f"{ROUTE} 65530: no rows parsed")
    # Keep the published 號次 even when a village's sequence is not 1..n
    # (e.g. 大樹區興田里 lists only 曾金益 as 2); flag it instead of renumbering.
    by_district: dict[str, list[int]] = {}
    for row in rows:
        by_district.setdefault(row["district"], []).append(int(row["number"]))
    for row in rows:
        nums = sorted(by_district[row["district"]])
        if nums != list(range(1, len(nums) + 1)):
            row["note"] = f"官方一覽表此里號次為 {nums}（非 1..n），照公告登錄"
    return rows


def mayor_council_rows() -> list[dict]:
    """65370 is a scanned image (no text layer). Its 106 entries were transcribed by
    hand into data/elections/2026/transcriptions/khec-65370.csv and every name was
    checked against the CEC registration roster for its district (all match, and
    every district's count equals its registrant count)."""
    import csv
    from model import DATA_DIR

    url = fetch.article_url(ROUTE, "65370")
    art = fetch.article(ROUTE, "65370")
    file_url = fetch.file_url(art["files"][0])
    fetched = fetch.meta(f"{fetch.BASE}/api/{ROUTE}/article/65370").get("fetchedAt", "")
    with (DATA_DIR / "transcriptions" / "khec-65370.csv").open(encoding="utf-8") as fh:
        return [{**r, "source": url, "sourceFile": file_url, "fetchedAt": fetched,
                 "note": "掃描檔人工轉錄，已與中選會登記名冊逐筆比對"} for r in csv.DictReader(fh)]


def main() -> int:
    rows = village_rows() + mayor_council_rows()
    path = write_numbers(ROUTE, rows)
    print(path, len(rows))
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
