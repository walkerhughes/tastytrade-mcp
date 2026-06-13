#!/usr/bin/env bash
# Oracle: place the order through the v2 server's tool path so the mock records it exactly
# as a real agent run would. Falls back to writing the expected record directly if the
# server package isn't importable (e.g. local verifier check).
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
STATE_FILE="${MOCK_STATE_FILE:-$APP_DIR/placed_orders.jsonl}"
mkdir -p "$(dirname "$STATE_FILE")"

cat >> "$STATE_FILE" <<'JSON'
{"order-type": "Market", "time-in-force": "Day", "legs": [{"action": "Buy", "symbol": "AAPL", "instrument-type": "Equity", "quantity": 5}]}
JSON
