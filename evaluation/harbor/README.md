# Harbor benchmark (v1 vs v2)

This benchmark runs Claude Code against the v1 server (`main`) and the v2 server
(`mcp-server-refactor`) over the same set of tasks, using the
[Harbor](https://github.com/laude-institute/harbor) framework. The agent is the same in both
runs and only the MCP server changes, so any difference in success rate, tool calls, tokens,
or latency comes from the server itself.

Every task runs against the mock Tastytrade API in `tests/fixtures/mock_api`, so the answers
are fixed and reproducible and no run touches a real account or live market data.

## Layout

```
harbor/
  environment/
    Dockerfile            # python and uv, both server checkouts, the mock API
    scripts/              # require-local-api, start-mock, mcp-v1, mcp-v2
  tasks/<name>/
    task.toml             # task config
    instruction.md        # the prompt the agent sees
    tests/test.sh         # verifier, writes a reward to /logs/verifier/reward.txt
    solution/solve.sh     # oracle, writes the known-correct answer
  job.yaml                # runs the v1 and v2 agents over every task
  generate_tasks.py       # regenerates the tasks from the fixtures
  validate_local.sh       # checks every verifier without Harbor or Docker
```

## Tasks (12)

Ten tasks ask for a single number (portfolio P/L, largest drawdown, ATM strike, IV rank,
total fees, net cash, latest dividend, net liquidating value, position count, and the fees on
a previewed vertical spread). One asks for the symbols in a watchlist. The last asks the agent
to place an order, and its verifier reads the order the mock recorded rather than a file the
agent wrote.

Nothing in the tasks is hand-typed. `generate_tasks.py` computes every expected answer from
the mock fixtures by running the same shaping code the server uses, so a task can never
disagree with the data the agent sees. The two anchor values are a total unrealized P/L of
+$700 and an SPY ATM strike of 200. Regenerate after changing a fixture:

```bash
python evaluation/harbor/generate_tasks.py
```

## Run it

```bash
# 1. Build the agent image. It clones both server versions and the mock API.
docker build -t tastytrade-bench evaluation/harbor/environment

# 2. Run both servers over every task, three trials each.
export ANTHROPIC_API_KEY=...
harbor run -c evaluation/harbor/job.yaml

# 3. Compare the two side by side.
harbor view jobs
```

The tasks reference the image by name (`docker_image = "tastytrade-bench"`), so build it
before the first run. Each trial's `result.json` records the reward, the phase timings, and
the token and cost totals, so success rate, tokens, tool calls, and latency per server come
straight out of the job directory.

## Check the verifiers without Harbor

`validate_local.sh` runs each task's oracle (`solve.sh`), then its verifier (`test.sh`), and
confirms the verifier awards a reward of 1. It then feeds an empty answer and confirms the
reward is 0. This is the local stand-in for `harbor run -a oracle`:

```bash
bash evaluation/harbor/validate_local.sh
# 12 passed, 0 failed
```

## Safety

The agent never sees real credentials. The image sets `API_BASE_URL` to the local mock and
uses throwaway credentials, and `require-local-api` refuses to start a server unless
`API_BASE_URL` points at localhost. Even the order-placement task only reaches the mock, which
records the order to a file the verifier reads.

The mock runs in the container as a background process that the server wrapper starts on
first use, so the benchmark is not tied to the local Docker provider the way a multi-container
setup would be. `network_mode: public` is set so the agent can reach the Anthropic API; the
Tastytrade calls stay on localhost.
