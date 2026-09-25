#!/usr/bin/env bash
# Usage: tools/shot.sh <path e.g. /spectrum/> <out.png> [width=1440] [height=2000] [theme=dark|light]
# Requires: python3 -m http.server 8743 --directory site  (running)
# Headless Chrome enforces a 500px minimum window width, so widths < 500 are
# rendered inside an exact-width iframe (file:// wrapper) and cropped.
set -euo pipefail
P="${1:-/}"; OUT="${2:-/tmp/shot.png}"; W="${3:-1440}"; H="${4:-2000}"; THEME="${5:-dark}"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ "$THEME" = "dark" ]; then P="${P}$( [[ "$P" == *\?* ]] && echo "&" || echo "?" )theme=dark"; fi
if [ "$THEME" = "light" ]; then P="${P}$( [[ "$P" == *\?* ]] && echo "&" || echo "?" )theme=light"; fi
URL="http://127.0.0.1:8743${P}"
WIN_W="$W"
if [ "$W" -lt 500 ]; then
  WRAP="$(mktemp -d)/wrap.html"
  printf '<!doctype html><html><body style="margin:0;background:#888"><iframe src="%s" style="border:0;display:block;margin:0 auto;width:%spx;height:%spx"></iframe></body></html>' "$URL" "$W" "$H" > "$WRAP"
  URL="file://$WRAP"; WIN_W=500
fi
timeout 90 "$CH" --headless=new --disable-gpu --hide-scrollbars --window-size="${WIN_W},${H}" \
  --virtual-time-budget=8000 --user-data-dir="$(mktemp -d)" --allow-file-access-from-files \
  --screenshot="$OUT" "$URL" >/dev/null 2>&1 || true
if [ "$WIN_W" != "$W" ]; then sips -c "$H" "$W" "$OUT" >/dev/null 2>&1 || true; fi
ls -la "$OUT"
