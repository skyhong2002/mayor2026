#!/usr/bin/env python3
"""嘉義市選舉委員會 → data/elections/2026/numbers/cyec.csv

號次抽籤結果 (text-layer PDF tables: 抽籤號次, 姓名, 性別, 出生年月日, 推薦之政黨):
* 65350 嘉義市第12屆市長選舉候選人姓名號次抽籤結果
* 65355 / 65382 嘉義市議會第12屆議員選舉第1 / 第2選舉區候選人姓名號次抽籤結果
* 65444 嘉義市第12屆里長選舉候選人姓名號次抽籤結果

選舉公報 (2026-11-12) — the more authoritative publication:
* 65775 市長選舉公報, 65777 議員選舉公報 (text layer): every candidate block
  (號次, 姓名, 性別, 出生年, 推薦之政黨) is read by position and must agree with the
  draw table; those rows then cite the 公報.
* 65782 里長選舉公報 is image-only (no text layer), so 里長 rows cite the draw result.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/cyec.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fetch  # noqa: E402
from numbers_common import check, norm_name, write_numbers  # noqa: E402

ROUTE = "cyec"
COUNTY = "嘉義市"
DRAWS = {"65350": "county-mayor", "65355": "county-councilor", "65382": "county-councilor", "65444": "village-chief"}
GAZETTES = {"65775": "county-mayor", "65777": "county-councilor"}


def clean(cell: str | None) -> str:
    return re.sub(r"\s+", "", cell or "")


def draw_rows() -> list[dict]:
    import pdfplumber

    out = []
    for art_id, category in DRAWS.items():
        art = fetch.article(ROUTE, art_id)
        url = fetch.article_url(ROUTE, art_id)
        for file_name in art["files"]:
            file_url = fetch.file_url(file_name)
            fetched = fetch.meta(file_url).get("fetchedAt", "")
            with pdfplumber.open(str(fetch.cached_file(file_name))) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables():
                        for cells in table:
                            cells = [clean(c) for c in cells]
                            if len(cells) < 6 or not cells[0].startswith(COUNTY) or not cells[1].isdigit():
                                continue
                            district, num, name, gender, born, party = cells[:6]
                            m = re.match(r"(\d{2,3})/\d{2}/\d{2}$", born)
                            if not m:
                                raise SystemExit(f"{file_name}: bad 出生年月日 {cells}")
                            out.append({"category": category, "district": district, "number": num, "name": name,
                                        "gender": gender, "birthYear": str(int(m.group(1)) + 1911), "party": party,
                                        "source": url, "sourceFile": file_url, "fetchedAt": fetched})
    return out


def gazette_candidates(path: Path) -> list[dict]:
    """Candidate blocks of a CEC-template 選舉公報 page with a text layer.

    Each block is anchored on the 48pt 號次; the 24pt word(s) under it are the name,
    the ROC birth year sits just above 出生年月日, 性別：X, and the party is the 12pt
    word under 推薦之政黨.
    """
    import pdfplumber

    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            anchors = [w for w in words if round(w["size"]) == 48 and w["text"].isdigit()]
            for a in anchors:
                x0, y0 = a["x0"] - 90, a["top"] - 5
                below = [b["top"] for b in anchors if abs(b["x0"] - a["x0"]) < 60 and b["top"] > a["top"] + 50]
                y1 = min(below) - 5 if below else page.height
                block = [w for w in words if x0 <= w["x0"] <= x0 + 700 and y0 <= w["top"] < y1 and w is not a]
                name = "".join(w["text"] for w in sorted(
                    (w for w in block if round(w["size"]) == 24 and w["top"] < a["top"] + 80), key=lambda w: w["x0"]))
                gender = birth = party = ""
                g = [w for w in block if w["text"].startswith("性別")]
                if g:
                    gender = g[0]["text"].split("：")[-1].strip()
                lab = [w for w in block if w["text"].startswith("出生年月日")]
                if lab:
                    lb = lab[0]
                    yr = [w for w in block if -16 <= w["top"] - lb["top"] <= -3 and lb["x0"] + 50 <= w["x0"] <= lb["x0"] + 85]
                    digits = yr[0]["text"].lstrip("：:").strip() if yr else ""
                    birth = str(int(digits) + 1911) if digits.isdigit() else ""
                pl = [w for w in block if "之政黨" in w["text"]]
                if pl:
                    lp = pl[0]
                    party = "".join(w["text"] for w in sorted(
                        (w for w in block if 22 <= w["top"] - lp["top"] <= 38 and lp["x0"] - 50 <= w["x0"] <= lp["x1"] + 5
                         and "具結" not in w["text"] and round(w["size"]) == 12), key=lambda w: w["x0"]))
                out.append({"number": a["text"], "name": name, "gender": gender, "birthYear": birth, "party": party})
    return out


def apply_gazettes(rows: list[dict]) -> None:
    """Re-cite mayor/councilor rows to the 公報 after checking every field matches."""
    for art_id, category in GAZETTES.items():
        art = fetch.article(ROUTE, art_id)
        url = fetch.article_url(ROUTE, art_id)
        for file_name in art["files"]:
            label = art["fileNames"][file_name]
            district = COUNTY if category == "county-mayor" else COUNTY + label
            file_url = fetch.file_url(file_name)
            fetched = fetch.meta(file_url).get("fetchedAt", "")
            gaz = {g["number"]: g for g in gazette_candidates(fetch.cached_file(file_name))}
            draw = {r["number"]: r for r in rows if r["category"] == category and r["district"] == district}
            if sorted(gaz) != sorted(draw):
                raise SystemExit(f"{label}: 公報 號次 {sorted(gaz)} != 抽籤結果 {sorted(draw)}")
            for num, row in draw.items():
                g = gaz[num]
                for field in ("name", "gender", "birthYear", "party"):
                    a, b = norm_name(g[field]), norm_name(row[field])
                    if a != b:
                        raise SystemExit(f"{label} #{num} {field}: 公報 {a!r} != 抽籤結果 {b!r}")
                row.update({"source": url, "sourceFile": file_url, "fetchedAt": fetched,
                            "note": f"與號次抽籤結果 {row['source']} 相符"})


def main() -> int:
    rows = draw_rows()
    apply_gazettes(rows)
    path = write_numbers(ROUTE, rows)
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
