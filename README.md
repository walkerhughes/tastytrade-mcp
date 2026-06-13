# tastytrade-mcp

An MCP server that connects [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to the [TastyTrade Open API](https://developer.tastytrade.com/getting-started/), giving Claude direct access to your brokerage account, market data, and order management.

## Features

12 tools, each built around a question a trader actually asks rather than a single REST
endpoint. Responses are trimmed and carry a computed summary, malformed arguments are
corrected where it's safe to, and errors come back with a suggestion instead of a stack
trace.

| Area | Tools |
|---|---|
| Accounts & portfolio | `list_accounts`, `get_portfolio`, `get_portfolio_history` |
| Market data | `search_symbols`, `get_market_data`, `get_option_chain` |
| Activity | `query_transactions`, `list_orders` |
| Trading | `preview_order`, `place_order`, `cancel_order` |
| Watchlists | `get_watchlists` |

- **`get_portfolio`** returns balances, positions, and a P/L rollup in one call.
- **`get_market_data`** is one snapshot covering quote, IV metrics, dividends, earnings, and instrument detail.
- **`get_option_chain`** lists expirations, then returns quote-enriched strikes plus a summary
  (ATM strike, IV range, busiest strikes by volume and open interest).
- **`query_transactions`** fetches once and then pages, searches, and sorts locally, with a cash and fee summary.

Authentication uses the OAuth2 refresh-token flow with automatic token refresh.

### Order safety

`place_order` executes live trades and is gated twice: the server must be started with
`TT_ENABLE_TRADING=true`, **and** each call must pass `confirm=true`. Otherwise the order is not
sent and the previewed effect is returned. Always call `preview_order` first.

## Architecture

The design follows the Honeycomb MCP: a few curated tools, responses shaped for a model rather
than a UI, and schemas that steer the model toward valid calls. See [`docs/design.md`](docs/design.md)
for the full reasoning.

- **Curated tools**, one module per group: [`src/tools/`](src/tools)
- **Response shaping and summaries**, trimmed payloads with computed rollups: [`src/shaping/`](src/shaping)
- **Typed argument schemas** that validate and [auto-correct](src/infra/correction.py) common mistakes: [`src/schemas/`](src/schemas)
- **Guided errors** that return a suggestion instead of a stack trace: [`src/infra/errors.py`](src/infra/errors.py)
- **Caching** with a per-resource TTL that also serves paging, search, and sort in memory: [`src/infra/cache.py`](src/infra/cache.py)
- **Shared pagination** across the list tools: [`src/infra/pagination.py`](src/infra/pagination.py)
- **Structured logging** to stderr, safe for a stdio server: [`src/infra/logging.py`](src/infra/logging.py)
- **Trading safety gate**, an env flag plus a per-call confirm: [`src/config.py`](src/config.py)
- **Deterministic mock API** for tests and evals: [`tests/fixtures/mock_api/`](tests/fixtures/mock_api)
- **Agent-loop evals** through Harbor: [`evals/`](evals)

## Getting Started

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure credentials

Copy `.env.example` to `.env` and fill in your TastyTrade API credentials:

```bash
cp .env.example .env
```

You'll need a registered OAuth client from TastyTrade. Set these values in `.env`:

```
TT_CLIENT_ID=<your client id>
TT_SECRET=<your client secret>
TT_REFRESH=<your refresh token>
API_BASE_URL=api.tastyworks.com
```

### 3. Run with Claude Code

The `.mcp.json` is already configured. Start Claude Code from the project directory and the TastyTrade MCP server will be available automatically.

## Example

Once running, you can ask Claude things like:

> "What are my current positions and P&L?"

Claude calls `list_accounts` to find your account number, then `get_portfolio` to fetch balances, positions, and P/L in a single call:

```
User: What are my current positions?

Claude: [calls list_accounts]  returns account XXXXXXXX
        [calls get_portfolio]  returns balances, positions, and a P/L summary

You have 3 open positions:
  AAPL  100 shares   +$320.50 (+2.1%)
  SPY   2 puts       -$45.00  (-8.3%)
  TSLA  5 calls      +$180.00 (+12.5%)

Net liquidating value: $12,345.67
```

You can also ask Claude to analyze option chains, check IV rank across symbols, preview trades before placing them, and manage live orders.

## Development

```bash
make check             # lint + typecheck + unit tests
make test-unit         # unit tests only
make coverage          # tests with coverage report
```

## Project Structure

```
├── src/
│   ├── client.py      # Tastytrade API client (OAuth2 auth, retry, logging)
│   ├── server.py      # FastMCP server: registers the tools
│   ├── config.py      # Env-driven settings (trading gate, cache TTLs)
│   ├── infra/         # errors, cache, correction, pagination, logging
│   ├── schemas/       # Pydantic argument schemas (validation + auto-correction)
│   ├── shaping/       # Response shaping + summary builders
│   └── tools/         # One module per tool group
├── tests/             # Unit and integration tests, plus the mock API fixtures
├── evals/             # Agent-loop eval tasks and the Harbor benchmark
├── docs/design.md     # Technical design doc
├── .mcp.json          # MCP server config for Claude Code
├── .env.example       # Credential template
└── pyproject.toml     # Dependencies and tool config
```
