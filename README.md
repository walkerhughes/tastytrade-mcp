# tastytrade-mcp

An MCP server that connects [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to the [TastyTrade Open API](https://developer.tastytrade.com/getting-started/), giving Claude direct access to your brokerage account, market data, and order management.

## Features

- **Account & Portfolio** — balances, positions, trading status, transaction history, net liq history
- **Order Management** — preview (dry-run), place, cancel, and replace orders
- **Market Data** — symbol search, equity info, option chains (with expiration/strike filtering), IV rank, liquidity metrics, dividends, earnings
- **Watchlists** — personal and public TastyTrade watchlists

Authentication uses OAuth2 refresh-token flow with automatic token refresh.

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

Claude will call `get_accounts` to find your account number, then `get_positions` to fetch your portfolio — all through the MCP server:

```
User: What are my current positions?

Claude: [calls get_accounts]  →  account XXXXXXXX
        [calls get_positions] →  returns portfolio data

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
│   ├── client.py      # TastyTrade API client (OAuth2 auth)
│   └── server.py      # MCP server with 22 tools
├── tests/unit/        # 44 unit tests (94% coverage)
├── .mcp.json          # MCP server config for Claude Code
├── .env.example       # Credential template
└── pyproject.toml     # Dependencies and tool config
```
