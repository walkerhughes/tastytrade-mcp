# Tastytrade MCP server design

The design follows the Honeycomb MCP write-up
[*"MCP, Easy as 1-2-3?"*](https://www.honeycomb.io/blog/mcp-easy-as-1-2-3): build a small set of
tools shaped for a model rather than wrapping each REST endpoint directly. A thin wrapper over
the API runs into three problems:

- Token volume is the main cost. API JSON is built for UIs and code, not for a model's context
  window. A full option chain or positions payload fills the window with fields the model never
  reads.
- Models get stuck on request shapes they don't know. Without argument correction and helpful
  errors, a model that gets an order leg or a chain filter slightly wrong will fail, adjust, fail
  again, and eventually simplify the request into something useless.
- Nothing is curated. Every field, every null, and every internal id is passed straight through,
  with no summaries, no derived figures, and no caching.

So the server provides a small set of higher-level tools, argument schemas that correct common
mistakes, errors that suggest a fix, summaries computed on the server, a cache that serves paging
locally, and an eval harness.

## Tools

| Tool | Covers |
|---|---|
| `list_accounts()` | accounts plus options level and restrictions |
| `get_portfolio(account_number="", include_closed=False)` | balances, positions, and a P/L `summary` |
| `get_portfolio_history(account_number="", time_back="1m")` | net-liq history downsampled to 30 points or fewer, with drawdown stats |
| `search_symbols(query)` | symbol search, trimmed to the useful fields |
| `get_market_data(symbols, include=["quote","metrics"])` | one per-symbol snapshot: quote, IV metrics, dividends, earnings, instrument |
| `get_option_chain(symbol, expiration="", strikes_near=10, dte_max=None, option_type=None, include_quotes=True)` | expirations, or strikes filtered and quote-enriched with a `summary` |
| `query_transactions(...)` | transactions fetched once, then paged, searched, and sorted from cache, with a `summary` |
| `list_orders(scope="live"\|"history", ...)` | live or historical orders |
| `preview_order(order, account_number="")` | dry run with shaped fees, buying power, and warnings |
| `place_order(order, account_number="", confirm=False, replace_order_id=None)` | live order, behind `TT_ENABLE_TRADING` and `confirm=true` |
| `cancel_order(order_id, account_number="")` | cancel a working order |
| `get_watchlists(name="")` | watchlist names, or one list's symbols |

Streaming quote tokens are intentionally left out, since they are no use without a streaming
client.

## Architecture

Built on FastMCP, Python 3.13, httpx, stdio, and Pydantic.

```
src/
  server.py            # FastMCP setup, instructions, register_all()
  client.py            # auth and transport, plus logging and 429 retry
  config.py            # settings: TT_ENABLE_TRADING, log level, cache TTLs
  infra/
    logging.py         # structured logging to stderr, safe for a stdio server
    errors.py          # @guarded_tool, turns failures into {error, suggestions}
    correction.py      # fixes common argument mistakes before validation
    cache.py           # TTLCache plus access_collection for local paging
    pagination.py      # shared PaginationParams
  schemas/             # Pydantic argument schemas
    common.py orders.py chain.py
  shaping/             # trimmed shapes and summary builders
    summarize.py portfolio.py chain.py transactions.py orders.py market_data.py
  tools/               # one module per group, each with register(mcp)
    accounts.py market_data.py options.py transactions.py orders.py watchlists.py
```

- The Pydantic schemas do two jobs. A `model_validator(mode="before")` corrects the arguments,
  and a `model_validator(mode="after")` checks them and raises with a clear message. FastMCP
  takes Pydantic models as tool parameters.
- `infra/errors.py` wraps every tool with `@guarded_tool`. It catches `httpx.HTTPStatusError`
  and `ValidationError` and returns a JSON object with an `error` message and a `suggestions`
  list that includes a correct example, never a stack trace.
- `infra/cache.py` keeps a per-resource TTL (quotes 15s, metrics 120s, transactions and chain
  300s, accounts and instruments 900s, live orders not cached) with an LRU cap.
  `access_collection` pages, searches, and sorts a cached list in memory, so repeated paging does
  not hit the API again.
- `infra/logging.py` writes structured logs to stderr, since stdout is the MCP channel. Each
  record carries the tool name, duration, whether the cache was hit, and the response size.

## Response shaping

Every tool returns a `summary` alongside its items. Decimal strings become rounded floats, nulls
and internal fields are dropped, and kebab-case keys become snake_case.

- `get_option_chain` summary: ATM strike, strike count, days to expiration, strike range, IV
  range, and the busiest strikes by volume and open interest. The nested chain endpoint has no
  quotes, so the tool makes one more batched `/market-data/by-type` call over the filtered symbols
  only. That is where the analysis and the token savings come from.
- `get_portfolio` summary: total P/L, day P/L, and exposure by underlying. A greeks rollup is
  deferred, since Tastytrade positions carry no greeks and it would need a per-option lookup.
- `query_transactions` summary: count, net cash effect, total fees, counts by type, and the date
  range.
- `get_portfolio_history`: downsample to 30 points or fewer with start, end, change, and max
  drawdown. The raw series is dropped.

## Order safety

`place_order` has two independent gates:

1. `TT_ENABLE_TRADING`, an env flag, off by default. With it off, `place_order` declines and
   explains why, while preview and cancel still work.
2. `confirm=true`, a required argument. Even with trading enabled, a call without it is declined
   and the previewed effect is echoed back.

## Evals and the benchmark

The server is evaluated at the agent-loop level, where it actually runs. There are two layers.

- The fast checks are deterministic unit tests (`tests/unit/test_misuse_evals.py`). They feed
  realistic model mistakes through correction and validation and confirm the corrections and the
  suggestion-bearing errors. They run in CI.
- The Harbor benchmark (`evals/`) runs Claude Code over 12 tasks against two builds of the
  server, this one and a plain baseline that exposes each REST endpoint as its own tool, to
  measure what the curation buys. Harbor records the reward, phase timings, and token and cost
  totals, and `harbor view jobs` shows the two side by side. `evals/validate_local.sh` checks each
  task's verifier against its oracle without Harbor or an API key, so it runs in CI.

Both rely on the mock Tastytrade API in `tests/fixtures/mock_api`, a small ASGI app that replays
scrubbed responses, fakes `/oauth/token`, and records submitted orders so a verifier can check
them. The server reaches it through `API_BASE_URL`.

## What the curation buys

With both builds pointed at the mock API and asked for the same results, the win is fewer tool
calls and answers that are ready to use:

| Question | Endpoint-wrapper baseline | This server |
|---|---|---|
| Total unrealized P/L | 2 calls (`get_balances` and `get_positions`, then the model does the math) | 1 call (`get_portfolio`, P/L already in the summary) |
| SPY 2026-04-17 chain with ATM and per-strike IV and volume | 3 calls (`get_option_expirations`, `get_option_chain`, `get_quote`, then the model finds ATM) | 1 call (`get_option_chain`, enriched, with a summary) |
| Market snapshot (quote and IV metrics) | 2 calls (`get_quote` and `get_market_metrics`) | 1 call (`get_market_data`) |

Per-response size is close on these small fixtures, since the summaries and inline quotes add
bytes. The trimming pulls ahead on real Tastytrade payloads, which carry dozens of fields per
object. The full comparison, covering agent-loop tokens, tool-call counts, latency, and success
rate, is the Harbor benchmark in `evals/` (run `harbor run -c job.yaml` from there).

## Deferred work

- A greeks rollup in `get_portfolio` needs a per-option lookup.
- A UI deep-link tool, the equivalent of Honeycomb's `get_trace_link`, is skipped because the
  Tastytrade web URL format is not documented.
- The LLM eval run is manual and needs `ANTHROPIC_API_KEY`, so it does not block CI. The
  `--dry-run` oracle pass does run in CI.
