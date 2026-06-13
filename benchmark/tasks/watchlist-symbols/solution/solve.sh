#!/usr/bin/env bash
# Oracle: write the known-correct answer.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"symbols": ["AAPL", "MSFT"]}' > "$APP_DIR/answer.json"
