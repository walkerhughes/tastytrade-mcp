# Claude Code Development Guidelines

## Project Structure

```
├── src/                     # Application source code
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── unit/                # Fast, isolated unit tests
│   └── integration/         # Tests involving external systems
├── pyproject.toml           # Project config, dependencies, tool settings
├── Makefile                 # Common dev commands
└── .claude/
    └── settings.json        # Hooks for auto-linting on .py edits
```

## Environment

- **Python**: >=3.13, managed via `uv`
- **Dependencies**: `uv sync` to install; dev deps (pytest, ruff, mypy, etc.) in `[dependency-groups.dev]`
- **Run commands**: Always use `uv run <command>` (e.g., `uv run pytest`)

## Testing

Follow **Test-Driven Development (TDD)**: Red -> Green -> Refactor.

- `make test`: run all tests
- `make test-unit`: run tests marked `@pytest.mark.unit`
- `make test-integration`: run tests marked `@pytest.mark.integration`
- `make coverage`: run tests with coverage report (80% threshold)
- Place shared fixtures in `tests/conftest.py`
- Unit tests: fast, no external dependencies
- Integration tests: may use databases, APIs, or services

## Linting & Formatting

- `make lint`: check with ruff
- `make lint-fix`: auto-fix with ruff
- `make format`: format with ruff

A PostToolUse hook automatically runs `make lint-fix format` after any `.py` file edit.

## Git Workflow

### Worktrees
- Use git worktrees for parallel development. Each task gets its own worktree.
- Never switch branches in the current worktree.

### Stacked PRs
- Prefer small, focused PRs (~200-400 lines) that stack on each other.
- Each PR should represent one logical change.
- Use `gh` CLI for all GitHub interactions (PRs, issues, labels).

### Commits
- Atomic commits with conventional-commit messages: `feat|fix|chore(#issue): description`
- Each commit should compile and pass tests independently.
- Commit and push frequently.

### Task Scoping
- Stay focused on the assigned task.
- Discovered bugs/tech debt: create a GitHub issue via `gh issue create`.
- Minor improvements: leave a `TODO` comment.
- Tangential/speculative work: ignore it.

## Workflow

1. **Plan first** for non-trivial tasks (3+ steps or architectural decisions).
2. **Use subagents** to keep the main context window clean.
3. **Verify before done**: run tests, check logs, demonstrate correctness.
4. **No laziness**: find root causes, no temporary fixes.
5. **Minimal impact**: only touch what's necessary.
6. **Simplicity first**: make every change as simple as possible.
