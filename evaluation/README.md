# Evaluation

Everything for testing and benchmarking the server lives here.

- **`run.py` and `cases/`** are the LLM eval harness. `make eval-dry` runs each case's oracle
  script with no API key (this also runs in CI), and `make eval` has Claude drive the tools
  through the Anthropic API and scores the answers.
- **`harbor/`** is the Harbor benchmark that pits the v1 server (`main`) against the v2 server
  (`mcp-server-refactor`) over the same tasks, with Claude Code as the agent. See
  [`harbor/README.md`](harbor/README.md).

The fast deterministic checks for argument correction and error guidance are unit tests, in
`tests/unit/test_misuse_evals.py`.

Both halves run against the mock Tastytrade API in `tests/fixtures/mock_api`, so results are
reproducible and nothing touches a real account.
