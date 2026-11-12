#!/usr/bin/env python3
"""新竹縣選舉委員會 → data/elections/2026/numbers/hccec.csv

* 65398 115年地方公職人員選舉候選人姓名號次抽籤結果（2026-10-27；5 個 PDF 附件
  「115年新竹縣縣長/縣議員/鄉鎮市長/鄉鎮市民代表/村里長選舉候選人(號次)抽籤結果」，
  欄位僅 選舉區/抽籤號次/姓名 — 無性別、政黨）

CEC export layout like 彰化縣 (3-column variant), so the PDF reader is shared with chec.py.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/hccec.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chec import draw_pdf_rows  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "hccec"
COUNTY = "新竹縣"
ARTICLE = "65398"


def main() -> int:
    path = write_numbers(ROUTE, draw_pdf_rows(ROUTE, COUNTY, ARTICLE))
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
