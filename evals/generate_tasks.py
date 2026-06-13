"""Generate the Harbor benchmark tasks.

Every expected answer is computed here from the mock API fixtures by running the same
shaping code the server uses. Nothing is typed in by hand, so a task answer can never drift
away from the data the agent actually sees. Change a fixture in
`tests/fixtures/mock_api/data.py` and rerun this script to refresh the tasks.

Run: python evals/generate_tasks.py
"""

import json
import os
import stat
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.shaping.chain import collect_symbols, select_strikes, shape_chain  # noqa: E402
from src.shaping.market_data import shape_market_data, shape_metrics  # noqa: E402
from src.shaping.portfolio import shape_balances, shape_history, shape_portfolio  # noqa: E402
from src.shaping.transactions import shape_transaction, summarize_transactions  # noqa: E402
from tests.fixtures.mock_api import data as fx  # noqa: E402

TASKS_DIR = os.path.join(os.path.dirname(__file__), "tasks")


# Compute the ground truth straight from the fixtures.


def _portfolio():
    return shape_portfolio(fx.BALANCES["data"], fx.POSITIONS["data"]["items"])["summary"]


def _transactions():
    rows = [shape_transaction(t) for t in fx.TRANSACTIONS["data"]["items"]]
    return summarize_transactions(rows)


def _atm_strike():
    items = fx.OPTION_CHAIN["data"]["items"]
    meta, strikes = select_strikes(items, "2026-04-17", strikes_near=0)
    symbols = collect_symbols(strikes, "")
    quotes = {s: fx.QUOTES[s] for s in symbols if s in fx.QUOTES}
    return shape_chain(meta, strikes, quotes, "")["summary"]["atm_strike"]


def _latest_dividend():
    items = fx.DIVIDENDS["AAPL"]["data"]["items"]
    return shape_market_data("AAPL", None, None, items, None, None)["latest_dividend"]["amount"]


def _watchlist_symbols():
    entries = fx.WATCHLIST_DETAIL["My Tech"]["data"]["watchlist-entries"]
    return [e["symbol"] for e in entries]


# Each numeric task: directory name, prompt, the JSON key the agent must write, the value
# (pulled from the fixtures above), and the tolerance the verifier allows.
NUMERIC_TASKS = [
    (
        "portfolio-pnl",
        "Find my total unrealized profit/loss across all open positions, in dollars.",
        "total_unrealized_pnl",
        _portfolio()["total_unrealized_pnl"],
        0.5,
    ),
    (
        "net-liq-drawdown",
        "Find my portfolio's largest drawdown over the available net-liq history, as a percent.",
        "max_drawdown_pct",
        shape_history(fx.NET_LIQ_HISTORY["data"]["items"])["summary"]["max_drawdown_pct"],
        0.05,
    ),
    (
        "option-chain-atm",
        "For SPY's 2026-04-17 expiration, find the at-the-money strike price.",
        "atm_strike",
        _atm_strike(),
        0.01,
    ),
    (
        "iv-rank-screen",
        "Find the current implied-volatility rank for AAPL.",
        "iv_rank",
        shape_metrics(fx.MARKET_METRICS["AAPL"])["iv_rank"],
        0.1,
    ),
    (
        "transaction-fee-total",
        "Find the total fees across all of my transactions, in dollars.",
        "total_fees",
        _transactions()["total_fees"],
        0.005,
    ),
    (
        "transaction-net-cash",
        "Find the net cash effect across all of my transactions, in dollars.",
        "net_cash_effect",
        _transactions()["net_cash_effect"],
        0.01,
    ),
    (
        "dividend-lookup",
        "Find AAPL's most recent dividend amount per share, in dollars.",
        "latest_dividend",
        _latest_dividend(),
        0.001,
    ),
    (
        "net-liq-value",
        "Find my account's current net liquidating value, in dollars.",
        "net_liquidating_value",
        shape_balances(fx.BALANCES["data"])["net_liquidating_value"],
        1.0,
    ),
    (
        "position-count",
        "Find how many open positions I currently hold.",
        "position_count",
        _portfolio()["position_count"],
        0.01,
    ),
    (
        "preview-vertical-spread",
        "Preview a 1-contract SPY 2026-04-17 200/205 call debit spread at a 1.50 limit and "
        "report the total fees, in dollars.",
        "total_fees",
        float(fx.DRY_RUN_TOTAL_FEES),
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

NUMERIC_INSTRUCTION = """\
# Task: {title}

{instruction}

Use the Tastytrade MCP tools to find the answer. Write it to `/app/answer.json` as a single
JSON object with this shape, and nothing else:

```json
{{"{key}": <number>}}
```
"""

NUMERIC_TEST = """\
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
LOG_DIR="${{LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOG_DIR"
reward=0
if python3 - "$APP_DIR/answer.json" <<'PY'
import json, sys

try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
    value = float(data[{key!r}])
    sys.exit(0 if abs(value - {expected!r}) <= {tol!r} else 1)
except Exception as exc:
    print(f"verifier error: {{exc}}", file=sys.stderr)
    sys.exit(1)
PY
then reward=1; fi
echo "$reward" > "$LOG_DIR/reward.txt"
echo "reward=$reward"
"""

NUMERIC_SOLVE = """\
#!/usr/bin/env bash
# Oracle: write the answer the fixtures imply, so the verifier itself can be checked.
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
mkdir -p "$APP_DIR"
echo '{{"{key}": {expected}}}' > "$APP_DIR/answer.json"
"""

CSV_INSTRUCTION = """\
# Task: {title}

{instruction}

Use the Tastytrade MCP tools to find the answer. Write it to `/app/answer.json` as a single
JSON object with this shape, and nothing else:

```json
{{"{key}": ["...", "..."]}}
```
"""

CSV_TEST = """\
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
LOG_DIR="${{LOG_DIR:-/logs/verifier}}"
mkdir -p "$LOG_DIR"
reward=0
if python3 - "$APP_DIR/answer.json" <<'PY'
import json, sys

try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
    got = sorted(s.upper() for s in data[{key!r}])
    sys.exit(0 if got == {expected!r} else 1)
except Exception as exc:
    print(f"verifier error: {{exc}}", file=sys.stderr)
    sys.exit(1)
PY
then reward=1; fi
echo "$reward" > "$LOG_DIR/reward.txt"
echo "reward=$reward"
"""

CSV_SOLVE = """\
#!/usr/bin/env bash
# Oracle: write the symbols the fixtures imply.
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
mkdir -p "$APP_DIR"
echo '{json_line}' > "$APP_DIR/answer.json"
"""

ORDER_INSTRUCTION = """\
# Task: Place an Order

Place a market order to buy 5 shares of AAPL in my account, and make sure it is actually
transmitted, not just previewed. Trading is enabled on this server. You do not need to write
any file; the brokerage records the submitted order.
"""

# The verifier reads the order the mock recorded, so it checks the order the agent really
# sent rather than a file the agent wrote about it.
ORDER_TEST = """\
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
"""

# The order the place-order task expects the agent to submit.
EXPECTED_ORDER = {
    "order-type": "Market",
    "time-in-force": "Day",
    "legs": [{"action": "Buy", "symbol": "AAPL", "instrument-type": "Equity", "quantity": 5}],
}

ORDER_SOLVE = """\
#!/usr/bin/env bash
# Oracle: record the order the agent is expected to place, so the verifier can be checked.
set -euo pipefail
APP_DIR="${{APP_DIR:-/app}}"
STATE_FILE="${{MOCK_STATE_FILE:-$APP_DIR/placed_orders.jsonl}}"
mkdir -p "$(dirname "$STATE_FILE")"
cat >> "$STATE_FILE" <<'JSON'
{json_line}
JSON
"""


def _write(path: str, content: str, executable: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(content)
    if executable:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _title(name: str) -> str:
    return name.replace("-", " ").title()


def generate() -> list[str]:
    names: list[str] = []

    for name, instruction, key, expected, tol in NUMERIC_TASKS:
        base = os.path.join(TASKS_DIR, name)
        _write(os.path.join(base, "task.toml"), TASK_TOML.format(name=name, desc=instruction.replace('"', "'")))
        _write(
            os.path.join(base, "instruction.md"),
            NUMERIC_INSTRUCTION.format(title=_title(name), instruction=instruction, key=key),
        )
        _write(
            os.path.join(base, "tests", "test.sh"),
            NUMERIC_TEST.format(key=key, expected=expected, tol=tol),
            executable=True,
        )
        _write(
            os.path.join(base, "solution", "solve.sh"),
            NUMERIC_SOLVE.format(key=key, expected=expected),
            executable=True,
        )
        names.append(name)

    # Watchlist listing (a list answer rather than a number).
    name = "watchlist-symbols"
    symbols = sorted(_watchlist_symbols())
    base = os.path.join(TASKS_DIR, name)
    instruction = "List the ticker symbols in my watchlist named 'My Tech'."
    _write(os.path.join(base, "task.toml"), TASK_TOML.format(name=name, desc=instruction))
    _write(
        os.path.join(base, "instruction.md"),
        CSV_INSTRUCTION.format(title=_title(name), instruction=instruction, key="symbols"),
    )
    _write(
        os.path.join(base, "tests", "test.sh"),
        CSV_TEST.format(key="symbols", expected=symbols),
        executable=True,
    )
    _write(
        os.path.join(base, "solution", "solve.sh"),
        CSV_SOLVE.format(json_line=json.dumps({"symbols": _watchlist_symbols()})),
        executable=True,
    )
    names.append(name)

    # Order placement (checked against the order the mock recorded).
    name = "place-limit-order"
    base = os.path.join(TASKS_DIR, name)
    desc = "Place a market order to buy 5 shares of AAPL, with confirmation."
    _write(os.path.join(base, "task.toml"), TASK_TOML.format(name=name, desc=desc))
    _write(os.path.join(base, "instruction.md"), ORDER_INSTRUCTION)
    _write(os.path.join(base, "tests", "test.sh"), ORDER_TEST, executable=True)
    _write(
        os.path.join(base, "solution", "solve.sh"),
        ORDER_SOLVE.format(json_line=json.dumps(EXPECTED_ORDER)),
        executable=True,
    )
    names.append(name)

    return names


if __name__ == "__main__":
    created = generate()
    print(f"Generated {len(created)} tasks:")
    for task in created:
        print(" -", task)
