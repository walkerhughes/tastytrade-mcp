"""Generate Harbor task directories from a compact spec.

Each task asks the agent to use the MCP tools to find a value and write it to
``/app/answer.json``. The verifier (``tests/test.sh``) checks that value against the
deterministic mock-API ground truth and writes a reward to
``/logs/verifier/reward.txt``. The oracle (``solution/solve.sh``) writes the known-correct
answer so the verifier itself can be validated with ``harbor run -a oracle`` (or locally
via ``validate_local.sh``).

Run: python benchmark/generate_tasks.py
"""

import os
import stat

HERE = os.path.dirname(__file__)
TASKS_DIR = os.path.join(HERE, "tasks")

# name, instruction, answer_key, kind, expected, tol
NUMERIC_TASKS = [
    (
        "portfolio-pnl",
        "Find my total unrealized profit/loss across all open positions (in dollars).",
        "total_unrealized_pnl",
        700.0,
        0.5,
    ),
    (
        "net-liq-drawdown",
        "Find my portfolio's maximum drawdown over the available net-liq history, as a percent.",
        "max_drawdown_pct",
        11.32,
        0.05,
    ),
    (
        "option-chain-atm",
        "For SPY's 2026-04-17 expiration, find the at-the-money (ATM) strike price.",
        "atm_strike",
        200.0,
        0.01,
    ),
    ("iv-rank-screen", "Find the current implied-volatility rank (IV rank) for AAPL.", "iv_rank", 42.5, 0.1),
    (
        "transaction-fee-total",
        "Find the total fees across all of my transactions (in dollars).",
        "total_fees",
        0.32,
        0.005,
    ),
    (
        "transaction-net-cash",
        "Find the net cash effect across all of my transactions (in dollars).",
        "net_cash_effect",
        524.0,
        0.01,
    ),
    (
        "dividend-lookup",
        "Find AAPL's most recent dividend amount per share (in dollars).",
        "latest_dividend",
        0.24,
        0.001,
    ),
    (
        "net-liq-value",
        "Find my account's current net liquidating value (in dollars).",
        "net_liquidating_value",
        52000.0,
        1.0,
    ),
    ("position-count", "Find how many open positions I currently hold.", "position_count", 2, 0.01),
    (
        "preview-vertical-spread",
        "Preview a 1-contract SPY 2026-04-17 200/205 call debit spread at a 1.50 limit; "
        "report the total fees (in dollars).",
        "total_fees",
        1.16,
        0.005,
    ),
]

TASK_TOML = """\
[task]
name = "{name}"
description = "{desc}"

[metadata]
suite = "tastytrade-mcp"

[environment]
docker_image = "tastytrade-bench"
network_mode = "public"

[agent]
timeout_sec = 300

[verifier]
timeout_sec = 60
"""

INSTRUCTION = """\
# Task: {title}

{instruction}

Use the available Tastytrade MCP tools to find the answer. When you have it, write a JSON
object to `/app/answer.json` with exactly this shape:

```json
{{"{key}": <number>}}
```

Write only that file. Do not include any other text in it.
"""

TEST_SH = """\
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
LOG_DIR="${{LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOG_DIR"
reward=0
if python3 - "$APP_DIR/answer.json" <<'PY'
import json, sys
key = {key!r}
expected = {expected!r}
tol = {tol!r}
try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
    val = float(data[key])
    sys.exit(0 if abs(val - float(expected)) <= float(tol) else 1)
except Exception as exc:
    print(f"verifier error: {{exc}}", file=sys.stderr)
    sys.exit(1)
PY
then reward=1; fi
echo "$reward" > "$LOG_DIR/reward.txt"
echo "reward=$reward"
"""

SOLVE_SH = """\
#!/usr/bin/env bash
# Oracle: write the known-correct answer so the verifier can be validated.
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
mkdir -p "$APP_DIR"
echo '{{"{key}": {oracle}}}' > "$APP_DIR/answer.json"
"""


def _write(path: str, content: str, executable: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    if executable:
        st = os.stat(path)
        os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def generate() -> list[str]:
    names = []
    for name, instruction, key, expected, tol in NUMERIC_TASKS:
        base = os.path.join(TASKS_DIR, name)
        title = name.replace("-", " ").title()
        _write(os.path.join(base, "task.toml"), TASK_TOML.format(name=name, desc=instruction.replace('"', "'")))
        _write(os.path.join(base, "instruction.md"), INSTRUCTION.format(title=title, instruction=instruction, key=key))
        _write(
            os.path.join(base, "tests", "test.sh"), TEST_SH.format(key=key, expected=expected, tol=tol), executable=True
        )
        _write(os.path.join(base, "solution", "solve.sh"), SOLVE_SH.format(key=key, oracle=expected), executable=True)
        names.append(name)
    return names


if __name__ == "__main__":
    created = generate()
    print(f"Generated {len(created)} numeric tasks:")
    for n in created:
        print(" -", n)
