"""Shared vocabulary for the 2026 (民國115年) local-election candidate dataset.

Pure stdlib, Python 3.9 — imported by the importer (dev box) *and* by the site
renderer on the scheduled machine.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "elections" / "2026"
CANDIDATES_CSV = DATA_DIR / "candidates.csv"
SOURCES_JSON = DATA_DIR / "sources.json"
RECONCILIATION_JSON = DATA_DIR / "reconciliation.json"
RECONCILIATION_MD = DATA_DIR / "reconciliation.md"

ELECTION_DAY = "2026-11-28"

# id → (label, short label, level). Order is the ballot order used everywhere.
CATEGORIES: dict[str, dict[str, str]] = {
    "municipal-mayor": {"label": "直轄市長", "short": "市長", "level": "county"},
    "county-mayor": {"label": "縣（市）長", "short": "縣市長", "level": "county"},
    "municipal-councilor": {"label": "直轄市議員", "short": "市議員", "level": "county"},
    "county-councilor": {"label": "縣（市）議員", "short": "縣市議員", "level": "county"},
    "township-mayor": {"label": "鄉（鎮、市）長", "short": "鄉鎮市長", "level": "township"},
    "indigenous-district-chief": {"label": "直轄市山地原住民區長", "short": "原住民區長", "level": "township"},
    "township-rep": {"label": "鄉（鎮、市）民代表", "short": "鄉鎮市民代表", "level": "township"},
    "indigenous-district-rep": {"label": "直轄市山地原住民區民代表", "short": "原住民區民代表", "level": "township"},
    "village-chief": {"label": "村（里）長", "short": "村里長", "level": "village"},
}

# 中選會 2026-09-07 新聞稿（https://web.cec.gov.tw/central/article/64711）
OFFICIAL_REGISTERED = {
    "municipal-mayor": 23, "municipal-councilor": 610, "county-mayor": 58, "county-councilor": 892,
    "indigenous-district-chief": 16, "indigenous-district-rep": 94, "township-mayor": 465,
    "township-rep": 3437, "village-chief": 14100,
}
OFFICIAL_SEATS = {
    "municipal-mayor": 6, "municipal-councilor": 381, "county-mayor": 16, "county-councilor": 538,
    "indigenous-district-chief": 6, "indigenous-district-rep": 50, "township-mayor": 198,
    "township-rep": 2076, "village-chief": 7780,
}
# 中選會 2026-10-16 審定（https://web.cec.gov.tw/central/article/65213）；
# lower levels are 審定 by each county commission and have no national total.
OFFICIAL_QUALIFIED = {
    "municipal-mayor": 23, "municipal-councilor": 605, "county-mayor": 58, "county-councilor": 887,
}
OFFICIAL_SOURCES = {
    "registered": "https://web.cec.gov.tw/central/article/64711",
    "roster": "https://web.cec.gov.tw/central/article/64709",
    "qualified": "https://web.cec.gov.tw/central/article/65213",
}

# County order = 中選會 ordering (直轄市 first, then 縣, then 市). Slugs of the six
# municipalities match the existing site (shell.CITY_ORDER) on purpose.
COUNTIES: list[tuple[str, str, str]] = [
    ("taipei", "臺北市", "mect"), ("new-taipei", "新北市", "tpcec"), ("taoyuan", "桃園市", "tyec"),
    ("taichung", "臺中市", "tcec"), ("tainan", "臺南市", "tnec"), ("kaohsiung", "高雄市", "khec"),
    ("yilan", "宜蘭縣", "ilec"), ("hsinchu-county", "新竹縣", "hccec"), ("miaoli", "苗栗縣", "mlec"),
    ("changhua", "彰化縣", "chec"), ("nantou", "南投縣", "ntec"), ("yunlin", "雲林縣", "ylec"),
    ("chiayi-county", "嘉義縣", "cycec"), ("pingtung", "屏東縣", "ptec"), ("taitung", "臺東縣", "ttec"),
    ("hualien", "花蓮縣", "hlec"), ("penghu", "澎湖縣", "phec"), ("kinmen", "金門縣", "kmec"),
    ("lienchiang", "連江縣", "lcec"), ("keelung", "基隆市", "klec"), ("hsinchu-city", "新竹市", "hcec"),
    ("chiayi-city", "嘉義市", "cyec"),
]
COUNTY_BY_NAME = {name: slug for slug, name, _ in COUNTIES}
COUNTY_NAME = {slug: name for slug, name, _ in COUNTIES}
COUNTY_ROUTE = {slug: route for slug, _, route in COUNTIES}
MUNICIPALITIES = {"taipei", "new-taipei", "taoyuan", "taichung", "tainan", "kaohsiung"}

# Normalized candidate row (data/elections/2026/candidates.csv).
FIELDS = [
    "id",            # stable: <county>-<category>-<districtKey>-<number>
    "category",      # CATEGORIES key
    "county",        # COUNTIES slug
    "township",      # 鄉鎮市區 (township-level and village categories), else ""
    "district",      # 選舉區 label: "第1選舉區" / "平地原住民選舉區" / township / village name
    "districtKey",   # url-safe key unique within county+category
    "village",       # 村里 name (village-chief only)
    "number",        # 號次 (int as text)
    "name",
    "gender",        # 男 / 女 / "" when no official 2026 source states it
    "birthYear",     # 西元年 / ""
    "party",         # 推薦之政黨 as officially printed; "無" = 未經政黨推薦
    "incumbent",     # "Y" when the CEC 2022 result DB lists this name as elected in the same district; else ""
    "numberSource",  # URL of the 號次 publication
    "numberFetchedAt",
    "rosterSource",  # URL of the registration roster entry
    "profileSource", # URL giving gender/birth year (if any)
]

PARTY_SHORT = {
    "中國國民黨": "國民黨", "民主進步黨": "民進黨", "台灣民眾黨": "民眾黨", "時代力量": "時代力量",
    "台灣基進": "台灣基進", "親民黨": "親民黨", "新黨": "新黨", "台灣綠黨": "綠黨", "台灣團結聯盟": "台聯黨",
    "台聯黨": "台聯黨", "社會民主黨": "社民黨", "司法改革黨": "司法改革黨", "無": "無黨籍",
}


def party_short(party: str) -> str:
    return PARTY_SHORT.get(party, party or "無黨籍")


def party_slug(party: str) -> str:
    """Matches shell.party_slug for the colour ring (dpp/kmt/tpp/jrp/none)."""
    short = party_short(party)
    return {"民進黨": "dpp", "國民黨": "kmt", "民眾黨": "tpp", "司法改革黨": "jrp"}.get(short, "none")
