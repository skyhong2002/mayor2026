#!/usr/bin/env bash
# Usage: tools/shot.sh <path e.g. /spectrum/> <out.png> [width=1440] [height=2000] [theme=dark|light]
# Requires: python3 -m http.server 8743 --directory site  (running)
set -euo pipefail
P="${1:-/}"; OUT="${2:-/tmp/shot.png}"; W="${3:-1440}"; H="${4:-2000}"; THEME="${5:-dark}"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ "$THEME" = "dark" ]; then P="${P}$( [[ "$P" == *\?* ]] && echo "&" || echo "?" )theme=dark"; fi
if [ "$THEME" = "light" ]; then P="${P}$( [[ "$P" == *\?* ]] && echo "&" || echo "?" )theme=light"; fi
timeout 90 "$CH" --headless=new --disable-gpu --hide-scrollbars --window-size="${W},${H}" \
  --virtual-time-budget=6000 --user-data-dir="$(mktemp -d)" \
  --screenshot="$OUT" "http://127.0.0.1:8743${P}" >/dev/null 2>&1 || true
ls -la "$OUT"
