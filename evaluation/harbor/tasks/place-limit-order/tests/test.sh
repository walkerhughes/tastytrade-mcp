#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
STATE_FILE="${MOCK_STATE_FILE:-$APP_DIR/placed_orders.jsonl}"
mkdir -p "$LOG_DIR"
reward=0
if [ -f "$STATE_FILE" ] && python3 - "$STATE_FILE" <<'PY'
import json, sys

ok = False
with open(sys.argv[1]) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        order = json.loads(line)
        if str(order.get("order-type", "")).lower() != "market":
            continue
        for leg in order.get("legs", []):
            symbol = str(leg.get("symbol", "")).upper()
            qty = int(leg.get("quantity", 0))
            action = str(leg.get("action", "")).lower()
            if symbol == "AAPL" and qty == 5 and "buy" in action:
                ok = True
sys.exit(0 if ok else 1)
PY
then reward=1; fi
echo "$reward" > "$LOG_DIR/reward.txt"
echo "reward=$reward"
