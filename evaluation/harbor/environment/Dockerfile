# Benchmark agent environment.
#
# Provides two checkouts of the MCP server (v1 = main, v2 = mcp-server-refactor) plus the
# deterministic mock Tastytrade API, so Claude Code can be benchmarked against each server
# over identical tasks. Harbor installs the claude-code agent into this container itself.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv for dependency management (matches the project toolchain).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ARG REPO=https://github.com/walkerhughes/tastytrade-mcp
ARG V1_REF=main
ARG V2_REF=mcp-server-refactor

# Two server versions. The mock API and fixtures live in the v2 checkout and serve both.
RUN git clone --depth 1 --branch ${V1_REF} ${REPO} /opt/mcp-v1 \
    && git clone --depth 1 --branch ${V2_REF} ${REPO} /opt/mcp-v2
RUN cd /opt/mcp-v1 && uv sync --frozen || uv sync
RUN cd /opt/mcp-v2 && uv sync --frozen || uv sync

COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/require-local-api /usr/local/bin/start-mock \
    /usr/local/bin/mcp-v1 /usr/local/bin/mcp-v2

WORKDIR /app
# Both servers talk to the mock API with throwaway credentials. require-local-api also
# enforces the localhost target at startup, so the benchmark can never reach a real account.
ENV API_BASE_URL=http://localhost:8080 \
    TT_CLIENT_ID=test \
    TT_SECRET=test \
    TT_REFRESH=test \
    TT_ENABLE_TRADING=true \
    MOCK_STATE_FILE=/app/placed_orders.jsonl
