# 2026 地方選舉候選人名單與號次（資料層）

2026-11-28 投票的九合一地方選舉，全部九類候選人：直轄市長、縣（市）長、直轄市議員、縣（市）議員、
鄉（鎮、市）長、直轄市山地原住民區長、鄉（鎮、市）民代表、直轄市山地原住民區民代表、村（里）長。
只用官方來源；不使用新聞、維基、社群平台或 Apify。六都市長既有的貼文追蹤不受影響，其他候選人只有
基本資料、號次與來源（頁面標示「尚未追蹤社群貼文」）。

## 來源

| 用途 | 來源 |
|---|---|
| 登記名冊（姓名、選舉區、登記時推薦政黨） | 中選會〈115年地方公職人員選舉候選人登記名冊〉 <https://web.cec.gov.tw/central/article/64709>（13 份 PDF） |
| 登記人數、應選名額（官方總數） | 中選會 9/7 新聞稿 <https://web.cec.gov.tw/central/article/64711> |
| 中選會審定（市長、議員） | 中選會 10/16 新聞稿 <https://web.cec.gov.tw/central/article/65213> |
| 號次（以及部分性別、出生年、政黨） | 各直轄市、縣（市）選委會的號次抽籤結果／候選人名單公告／選舉公報，見 `numbers/<route>.py` 與 `sources.json` |
| 「2022 當選」（現任推定） | 中選會選舉資料庫 <https://data.cec.gov.tw/選舉資料庫/votedata.zip>，2022 地方選舉同類別、同縣市（鄉鎮市／村里）、同姓名之當選人 |
| 未列入號次的佐證 | 各選委會委員會議紀錄、審定公告、第二次登記公告（`explanations-*.csv` 的 `source` 欄） |

性別與出生年只在該縣市 2026 年的官方公告有印出時才填；不從 2022 資料或新聞推測。

## 檔案（`data/elections/2026/`）

| 檔案 | 內容 |
|---|---|
| `registered.csv`、`registered-seats.csv` | 中選會登記名冊與各選舉區應選名額（`parse_roster.py`） |
| `numbers/<route>.csv` | 各選委會號次，一列一位候選人（`scripts/elections/numbers/<route>.py`） |
| `transcriptions/*.csv` | 只有掃描影像、沒有文字層的官方公告，人工轉錄後逐筆與登記名冊比對（目前：高雄市長、市議員） |
| `manual.csv` | 姓名為造字或圖片、程式無法讀出的官方列（`add`／`rename`），每列附官方來源與說明 |
| `explanations-*.csv` | 每一個「登記但未見號次」「有號次但名冊無此人」差異的官方佐證（撤回、不合格、死亡、第二次登記、同一人異寫、`pending` 待公告） |
| `candidates.csv` | 合併後的公開名單（欄位見 `scripts/elections/model.py` 的 `FIELDS`） |
| `reconciliation.{md,json}` | 對帳報告：各類別登記／審定／號次／應選名額，與全部差異（已解釋、未解釋、待來源） |
| `sources.json` | 使用到的每個官方 URL、抓取時間與 sha256 |

## 流程

```bash
# 開發機（需網路；抓取經 fetch.py：全主機單一鎖、每次請求間隔 ≥1.5 秒、快取、最多重試 3 次）
uv run --no-project --with pdfplumber python3 scripts/elections/parse_roster.py
uv run --no-project --with pdfplumber --with xlrd python3 scripts/elections/numbers/<route>.py   # 逐一選委會
python3 scripts/elections/merge.py              # 需 state/elections/raw/vd2022（votedata.zip 解出 2022 地方選舉）
python3 scripts/build_election_data.py          # site/api/elections/2026/*、搜尋索引、RSS（排程每次都跑，純讀檔）
python3 -m unittest tests.test_elections_data
```

找新公告：`python3 scripts/elections/fetch.py lists <route> --since 20261110`（分頁列出各選單區塊，含置頂公告）、
`fetch.py menu <route>`、`fetch.py article <route> <id>`。

## 對帳規則

- 每一選舉區號次須為 1..n、不重複；例外（選委會公告本身如此）列在報告的「號次不連續」並由驗證器放行，新出現的缺號會讓建置失敗。
- 每位登記者若沒有號次，需在 `explanations-*.csv` 找到官方佐證才算「已解釋」；整個縣市類別尚未公告號次者為「待來源」；其他一律列為「未解釋」。
- 有號次但不在中選會登記名冊者，同樣需要佐證（多為第二次登記或姓名造字）。
- 縣市長、直轄市長、議員的號次人數與中選會審定人數比對。

## 已知限制（2026-11-13）

- 尚未公告號次：南投縣（全部）、連江縣（全部）、苗栗縣與屏東縣鄉鎮市層級、高雄市山地原住民區。
  直轄市議員、縣（市）長、縣（市）議員候選人名單法定公告日為 11/17，各鄉鎮市層級名單公告約同時；之後重跑對應 parser 即可補上。
- 部分選委會未公告不合格者姓名（或以○遮蔽），只能以人數比對；無法比對者列為未解釋。
