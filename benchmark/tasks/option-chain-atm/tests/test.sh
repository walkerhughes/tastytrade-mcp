#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
LOG_DIR="${LOG_DIR:-/logs/verifier}"
mkdir -p "$LOG_DIR"
reward=0
if python3 - "$APP_DIR/answer.json" <<'PY'
import json, sys
key = 'atm_strike'
expected = 200.0
tol = 0.01
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
    val = float(data[key])
    sys.exit(0 if abs(val - float(expected)) <= float(tol) else 1)
except Exception as exc:
    print(f"verifier error: {exc}", file=sys.stderr)
    sys.exit(1)
PY
then reward=1; fi
echo "$reward" > "$LOG_DIR/reward.txt"
echo "reward=$reward"
