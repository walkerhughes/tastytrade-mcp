# Tastytrade MCP benchmark (v1 vs v2)

Benchmarks **Claude Code** against the **v1** server (`main`) and the **v2** server
(`mcp-server-refactor`) over identical tasks, using the
[Harbor](https://github.com/laude-institute/harbor) framework. Claude Code is held constant;
the MCP server is the experimental variable, so differences in success rate, tool-call
count, tokens, and latency are attributable to the server design.

Everything runs against the deterministic **mock Tastytrade API**
(`tests/fixtures/mock_api`), so rewards are reproducible and no real credentials or live
market data are involved.

## Layout

```
benchmark/
  environment/
    Dockerfile            # python+uv, two server checkouts (v1, v2), mock API
    scripts/{start-mock,mcp-v1,mcp-v2}
  tasks/<name>/
    task.toml             # Harbor task config
    instruction.md        # the prompt given to the agent
    tests/test.sh         # verifier -> /logs/verifier/reward.txt
    solution/solve.sh     # oracle (known-correct answer)
  job.yaml                # two agent configs (mcp-v1 vs mcp-v2) over all tasks
  generate_tasks.py       # regenerates the numeric tasks from a spec
  validate_local.sh       # validates every verifier without Harbor/Docker
```

## Tasks (12)

Ten numeric/extraction tasks (portfolio P/L, max drawdown, ATM strike, IV rank,
transaction fees & net cash, dividend, net liq, position count, vertical-spread preview
fees), one watchlist listing, and one order-placement task verified by inspecting the
order the mock recorded. Each has a deterministic ground-truth answer baked into the
fixtures (e.g. total unrealized P/L = **+$700**, SPY ATM strike = **200**).

## Run it

```bash
# 1. Build the agent environment image (clones both server versions + mock API).
docker build -t tastytrade-bench benchmark/environment

# 2. Run the A/B benchmark (both server versions, 3 trials each, over all tasks).
export ANTHROPIC_API_KEY=...
harbor run -c benchmark/job.yaml

# 3. Compare results side-by-side (reward, tokens, tool calls, latency).
harbor view jobs
```

Each trial's `result.json` carries the verifier reward, phase timings, and token/cost
totals natively — so per-server **success rate, mean tokens, mean tool calls, and mean
latency** come straight out of the job directory.

## Validate verifiers without Harbor

`validate_local.sh` runs each task's oracle (`solve.sh`) then its verifier (`test.sh`) and
asserts reward 1, plus a negative control (empty answer → reward 0). This is the local
stand-in for `harbor run -a oracle`:

```bash
bash benchmark/validate_local.sh
# -> 12 passed, 0 failed
```

## Notes

- The mock API runs in-container as a background process started idempotently by the MCP
  server wrapper scripts, so the suite is not constrained to the local Docker provider the
  way a multi-container compose setup would be.
- `network_mode: public` is set so Claude Code can reach the Anthropic API; the Tastytrade
  calls stay local (the mock on `localhost:8080`).
- Regenerate numeric tasks after editing the spec: `python benchmark/generate_tasks.py`.
