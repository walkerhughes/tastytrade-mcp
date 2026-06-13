#!/usr/bin/env bash
# Oracle: write the known-correct answer so the verifier can be validated.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"
echo '{"atm_strike": 200.0}' > "$APP_DIR/answer.json"
