# 開放資料 API

公開說明頁：<https://mayor2026.observe.tw/api/>（`scripts/render/apidocs.py`）。本文件是維運面的對照。

## 運作方式

- 不帶 query string 的 `/api/*.json`、`/feeds/*.json`：Caddy 直接送 `published/current` 的靜態檔（與以前相同）。
- 帶 query string 的請求，以及兩個虛擬端點 `/api/posts.json`、`/api/elections/2026/candidates.json`：
  Caddy 轉給 `scripts/api_server.py`（`127.0.0.1:8341`，launchd `tw.observe.mayor2026.api`）。
  它只讀 `published/current`（依 symlink 實際指向的 release 快取），發布新快照後自動換用新資料，不需重啟。
- 回應保留靜態檔結構；列表被切片，`count` 改為回傳筆數，另加 `total`、`offset`、`limit`、`next`。
- CORS：`Access-Control-Allow-Origin: *`（靜態檔由 Caddy 加，動態回應由 api_server 加）。
- 參數錯誤或端點不支援的參數 → 400 JSON；未知參數名稱（如 `?v=`）忽略。

## 參數

共通（所有列表端點）：`limit`、`offset`、`fields=a,b,c`。

| 端點 | 列表欄位 | 篩選 |
|---|---|---|
| `/api/latest.json`（最新 100 則） | `posts` | 貼文篩選 |
| `/api/posts.json`（全部貼文，僅動態） | `posts` | 貼文篩選 |
| `/api/posts/<id>.json` | `posts` | 貼文篩選 |
| `/feeds/<id>.json`（最近 50 則） | `posts` | 貼文篩選 |
| `/api/topic-index.json` | `posts` | 貼文篩選 |
| `/api/candidates.json` | `candidates` | `city` |
| `/api/sources.json` | `sources` | `candidate`、`city` |
| `/api/spectrum.json` | `candidates` | `candidate`、`city` |
| `/api/status.json` | `sources` | `candidate`、`platform` |
| `/api/cities.json` | `cities` | — |
| `/api/elections/2026/candidates.json`（平面列表，僅動態） | `candidates` | 選舉篩選、`sort=number\|name` |

貼文篩選：`candidate`、`city`、`platform`、`topic`（中文議題名）、`intent`（`self_initiated`／`responsive`）、
`since`／`until`（ISO 8601；`until` 不含）、`q`（內文關鍵字，空白分隔須全中）。逗號分隔可多選。

選舉篩選：`county`（ID 或中文名）、`category`、`township`、`district`（包含）、`districtKey`、`village`（包含）、
`party`（包含）、`incumbent=true|false`、`number`、`q`。

縣市巢狀檔 `/api/elections/2026/<county>.json` 與非列表端點不接受參數（400，訊息指向平面列表）。

## 範例

```text
https://mayor2026.observe.tw/api/latest.json?limit=10
https://mayor2026.observe.tw/api/posts.json?city=taipei&topic=交通&since=2026-11-01&limit=20
https://mayor2026.observe.tw/api/posts/chiang-wanan.json?platform=facebook&limit=5&fields=id,text,url,postedAt
https://mayor2026.observe.tw/api/elections/2026/candidates.json?county=taipei&category=municipal-mayor&sort=number
https://mayor2026.observe.tw/api/elections/2026/candidates.json?county=hsinchu-city&category=county-councilor&limit=50&offset=50
```

## 部署（sky-mini）

```bash
sed "s#/Users/REPLACE_ME#$HOME#g" deploy/tw.observe.mayor2026.api.plist > ~/Library/LaunchAgents/tw.observe.mayor2026.api.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/tw.observe.mayor2026.api.plist
curl -s http://127.0.0.1:8341/healthz
```

程式更新後：`launchctl kickstart -k gui/$(id -u)/tw.observe.mayor2026.api`。

Caddyfile `mayor2026.observe.tw` 區塊（放在 `@static` 之前）：

```caddyfile
header /api/* ?Access-Control-Allow-Origin "*"
header /feeds/* ?Access-Control-Allow-Origin "*"

@dynamic_api {
	path /api/*.json /feeds/*.json
	expression `{query} != "" || {path} in ["/api/posts.json", "/api/elections/2026/candidates.json"]`
}
handle @dynamic_api {
	reverse_proxy 127.0.0.1:8341
}
```

本機測試：`python3 scripts/api_server.py --site site --port 18341`；單元測試 `tests/test_api_server.py`。
