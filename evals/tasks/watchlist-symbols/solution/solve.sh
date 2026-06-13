#!/usr/bin/env bash
# Oracle: write the symbols the fixtures imply.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"symbols": ["AAPL", "MSFT"]}' > "$APP_DIR/answer.json"
