#!/usr/bin/env bash
# Oracle: record the order the agent is expected to place, so the verifier can be checked.
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
STATE_FILE="${MOCK_STATE_FILE:-$APP_DIR/placed_orders.jsonl}"
mkdir -p "$(dirname "$STATE_FILE")"
cat >> "$STATE_FILE" <<'JSON'
{"order-type": "Market", "time-in-force": "Day", "legs": [{"action": "Buy", "symbol": "AAPL", "instrument-type": "Equity", "quantity": 5}]}
JSON
