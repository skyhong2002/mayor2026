#!/usr/bin/env python3
"""宜蘭縣選舉委員會 → data/elections/2026/numbers/ilec.csv

* 65391 115年宜蘭縣地方公職人員選舉今日完成候選人號次抽籤（2026-10-27；5 個 PDF 附件
  「[115年縣市長/縣市議員/鄉鎮市長/鄉鎮市民代表/村里長選舉]候選人抽籤結果」，
  欄位 選舉區/姓名/性別/推薦之政黨/抽籤號次/備註）

Same CEC export layout as 彰化縣, so the PDF reader is shared with chec.py.

    uv run --no-project --with pdfplumber python3 scripts/elections/numbers/ilec.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from chec import draw_pdf_rows  # noqa: E402
from numbers_common import check, write_numbers  # noqa: E402

ROUTE = "ilec"
COUNTY = "宜蘭縣"
ARTICLE = "65391"


def main() -> int:
    path = write_numbers(ROUTE, draw_pdf_rows(ROUTE, COUNTY, ARTICLE))
    print(path)
    check(ROUTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
