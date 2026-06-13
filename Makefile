.PHONY: lint lint-fix format typecheck check test test-unit test-integration coverage install-hooks eval eval-dry mock-api

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

typecheck:
	uv run mypy src/

check: lint typecheck test-unit

test:
	uv run pytest

test-unit:
	uv run pytest -m unit

test-integration:
	uv run pytest -m integration

coverage:
	uv run pytest --cov --cov-report=term-missing

install-hooks:
	git config core.hooksPath .githooks

# eval-dry runs the deterministic oracle scripts and needs no API key, so it runs in CI.
# eval drives Claude through the Anthropic API (needs ANTHROPIC_API_KEY and `uv pip install anthropic`).
eval-dry:
	uv run python -m evaluation.run --dry-run

eval:
	uv run python -m evaluation.run

# Run the mock Tastytrade API on its own, the way the Harbor benchmark runs it.
mock-api:
	uv run uvicorn tests.fixtures.mock_api.app:app --host 0.0.0.0 --port 8080
