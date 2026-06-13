#!/usr/bin/env bash
# Oracle: write the answer the fixtures imply, so the verifier itself can be checked.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"net_liquidating_value": 52000.0}' > "$APP_DIR/answer.json"
