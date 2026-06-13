"""Run the LLM eval cases, either with Claude or with the oracle scripts, and score them.

There are two modes. With --dry-run, each case's oracle script runs directly against the
mock API and its result is checked. This needs no API key, so it runs in CI and confirms the
tools and the checks are wired up correctly. Without --dry-run, Claude drives the same tools
through the Anthropic API in a tool-use loop and the final answer is checked; tool calls,
tokens, and latency are recorded.

Both modes point the tools at a fresh mock API, so a run is deterministic and never touches
real credentials or live market data.

Usage:
  uv run python -m evaluation.run --dry-run
  ANTHROPIC_API_KEY=... uv run python -m evaluation.run --model claude-fable-5
"""

import argparse
import asyncio
import glob
import json
import os
import time
from typing import Any, Callable

import httpx

from src.client import TastyTradeClient
from src.server import build_server
from src.tools import base
from src.tools.accounts import get_portfolio, get_portfolio_history, list_accounts
from src.tools.market_data import get_market_data, search_symbols
from src.tools.options import get_option_chain
from src.tools.orders import cancel_order, list_orders, place_order, preview_order
from src.tools.transactions import query_transactions
from src.tools.watchlists import get_watchlists
from tests.fixtures.mock_api.app import build_app

TOOL_FUNCS: dict[str, Callable[..., Any]] = {
    "list_accounts": list_accounts,
    "get_portfolio": get_portfolio,
    "get_portfolio_history": get_portfolio_history,
    "search_symbols": search_symbols,
    "get_market_data": get_market_data,
    "get_option_chain": get_option_chain,
    "query_transactions": query_transactions,
    "list_orders": list_orders,
    "preview_order": preview_order,
    "place_order": place_order,
    "cancel_order": cancel_order,
    "get_watchlists": get_watchlists,
}

CASES_DIR = os.path.join(os.path.dirname(__file__), "cases")


def install_mock_client() -> None:
    """Point the tool layer at a fresh in-process mock API."""
    os.environ.setdefault("TT_CLIENT_ID", "test")
    os.environ.setdefault("TT_SECRET", "test")
    os.environ.setdefault("TT_REFRESH", "test")
    transport = httpx.ASGITransport(app=build_app())
    base.reset_state()
    base._client = TastyTradeClient(base_url="http://mock.local", transport=transport)
    base._cache = None


def load_cases() -> list[dict]:
    cases = []
    for path in sorted(glob.glob(os.path.join(CASES_DIR, "*.json"))):
        with open(path) as fh:
            cases.append(json.load(fh))
    return cases


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur.get(part)
    return cur


def _check(value: Any, check: dict) -> bool:
    if "equals" in check:
        return value == check["equals"]
    if "approx" in check:
        return abs(float(value) - float(check["approx"])) <= check.get("tol", 0.01)
    if "contains" in check:
        return check["contains"] in (value or "")
    return False


async def run_oracle(case: dict) -> dict:
    """Run the case's oracle script and check it. This is how we sanity-check a verifier."""
    install_mock_client()
    last: Any = None
    for step in case.get("script", []):
        func = TOOL_FUNCS[step["tool"]]
        last = json.loads(await func(**step.get("args", {})))
    chk = case.get("script_check")
    passed = True
    if chk:
        passed = _check(_dig(last, chk["path"]), chk)
    return {"name": case["name"], "passed": passed, "output": last}


async def run_llm(case: dict, model: str) -> dict:
    """Drive Claude in a tool-use loop and check the final answer + tool sequence."""
    import anthropic  # lazy: only needed for live runs

    mcp = build_server()
    tool_defs = [
        {"name": t.name, "description": t.description, "input_schema": t.inputSchema} for t in await mcp.list_tools()
    ]
    install_mock_client()
    client = anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": case["prompt"]}]
    used_tools: list[str] = []
    in_tok = out_tok = 0
    start = time.monotonic()

    for _ in range(8):
        resp = client.messages.create(model=model, max_tokens=1024, tools=tool_defs, messages=messages)
        in_tok += resp.usage.input_tokens
        out_tok += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
        if not tool_uses:
            break
        results = []
        for tu in tool_uses:
            used_tools.append(tu.name)
            out = await TOOL_FUNCS[tu.name](**tu.input)
            results.append({"type": "tool_result", "tool_use_id": tu.id, "content": out})
        messages.append({"role": "user", "content": results})

    answer = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
    ac = case.get("answer_check", {})
    passed = _check(answer, ac) if ac else True
    expected = case.get("expected_tools", [])
    tools_ok = all(t in used_tools for t in expected)
    return {
        "name": case["name"],
        "passed": passed and tools_ok,
        "answer_ok": passed,
        "tools_ok": tools_ok,
        "tool_calls": len(used_tools),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "latency_s": round(time.monotonic() - start, 2),
    }


async def main_async(args: argparse.Namespace) -> int:
    cases = load_cases()
    if not cases:
        print(f"No cases found in {CASES_DIR}")
        return 1
    results = []
    for case in cases:
        if args.dry_run:
            results.append(await run_oracle(case))
        else:
            results.append(await run_llm(case, args.model))

    print(f"\n{'CASE':28} {'PASS':5}", end="")
    if not args.dry_run:
        print(f" {'TOOLS':6} {'IN_TOK':8} {'OUT_TOK':8} {'LAT(s)':7}", end="")
    print()
    for r in results:
        line = f"{r['name']:28} {'PASS' if r['passed'] else 'FAIL':5}"
        if not args.dry_run:
            line += f" {r['tool_calls']:<6} {r['input_tokens']:<8} {r['output_tokens']:<8} {r['latency_s']:<7}"
        print(line)
    n_pass = sum(1 for r in results if r["passed"])
    print(f"\n{n_pass}/{len(results)} cases passed")
    return 0 if n_pass == len(results) else 1


def main() -> None:
    import logging

    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Tastytrade MCP tier-2 eval runner")
    parser.add_argument("--dry-run", action="store_true", help="Run oracle scripts only (no LLM, CI-safe).")
    parser.add_argument("--model", default="claude-fable-5", help="Anthropic model id for live runs.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
