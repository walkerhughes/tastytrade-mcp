# Benchmark agent environment.
#
# Provides two checkouts of the server, the baseline (main) and the candidate
# (mcp-server-refactor), plus the mock Tastytrade API, so Claude Code can be benchmarked
# against each one over the same tasks. Harbor installs the claude-code agent itself.
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv for dependency management (matches the project toolchain).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ARG REPO=https://github.com/walkerhughes/tastytrade-mcp
ARG BASELINE_REF=main
ARG CANDIDATE_REF=mcp-server-refactor

# Both checkouts. The mock API and fixtures live in the candidate checkout and serve both.
RUN git clone --depth 1 --branch ${BASELINE_REF} ${REPO} /opt/mcp-baseline \
    && git clone --depth 1 --branch ${CANDIDATE_REF} ${REPO} /opt/mcp-candidate
RUN cd /opt/mcp-baseline && uv sync --frozen || uv sync
RUN cd /opt/mcp-candidate && uv sync --frozen || uv sync

COPY scripts/ /usr/local/bin/
RUN chmod +x /usr/local/bin/require-local-api /usr/local/bin/start-mock \
    /usr/local/bin/mcp-baseline /usr/local/bin/mcp-candidate

WORKDIR /app
# Both servers talk to the mock API with throwaway credentials. require-local-api also
# enforces the localhost target at startup, so the benchmark can never reach a real account.
ENV API_BASE_URL=http://localhost:8080 \
    TT_CLIENT_ID=test \
    TT_SECRET=test \
    TT_REFRESH=test \
    TT_ENABLE_TRADING=true \
    MOCK_STATE_FILE=/app/placed_orders.jsonl
