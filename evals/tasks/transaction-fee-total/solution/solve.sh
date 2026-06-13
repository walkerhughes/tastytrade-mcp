#!/usr/bin/env bash
# Oracle: write the answer the fixtures imply, so the verifier itself can be checked.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"total_fees": 0.32}' > "$APP_DIR/answer.json"
