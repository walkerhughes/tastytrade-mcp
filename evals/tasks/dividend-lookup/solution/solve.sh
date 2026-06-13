#!/usr/bin/env bash
# Oracle: write the answer the fixtures imply, so the verifier itself can be checked.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"latest_dividend": 0.24}' > "$APP_DIR/answer.json"
