#!/usr/bin/env bash
# Usage: tools/shot.sh <path e.g. /spectrum/> <out.png> [width=1440] [height=2000] [theme=dark|light]
# Kept for old instructions; the screenshot itself is taken by tools/shot.mjs
# (Playwright, works on Linux and macOS). Needs a server on SHOT_BASE
# (default http://127.0.0.1:8743) and tools/node_modules linking to Playwright.
set -euo pipefail
exec node "$(dirname "$0")/shot.mjs" "$@"
