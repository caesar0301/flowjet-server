# Makefile for flowjet-server
UV_RUN ?= uv run
HOST ?= 0.0.0.0
PORT ?= 8080

.PHONY: help sync sync-dev sync-nano format format-check lint lint-fix \
	test test-sdk test-unit check run serve run-nano examples \
	examples-sdk examples-http examples-e2e build clean

help:
	@echo "flowjet-server"
	@echo ""
	@echo "  make sync           - Sync runtime dependencies"
	@echo "  make sync-dev       - Sync with dev extras (pytest, openai, ruff)"
	@echo "  make sync-nano      - Sync with nano + dev extras"
	@echo "  make format         - Format with ruff"
	@echo "  make format-check   - Check formatting (CI)"
	@echo "  make lint           - Lint with ruff"
	@echo "  make lint-fix       - Auto-fix lint issues"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit/API tests (exclude live SDK suite)"
	@echo "  make test-sdk       - Run OpenAI SDK compatibility tests"
	@echo "  make check          - format-check + lint + test"
	@echo "  make run / serve    - Start with deterministic fake backend"
	@echo "  make run-nano       - Start with real soothe-nano agent"
	@echo "  make examples       - Show how to run end-to-end examples"
	@echo "  make examples-sdk   - E2E via OpenAI Python SDK"
	@echo "  make examples-http  - E2E via raw HTTP (httpx)"
	@echo "  make examples-e2e   - Run both E2E example scripts"
	@echo "  make build          - Build dist/"
	@echo "  make clean          - Remove build/cache artifacts"

sync:
	uv sync

sync-dev:
	uv sync --extra dev

sync-nano:
	uv sync --extra nano --extra dev

format:
	$(UV_RUN) ruff format src/ tests/ examples/

format-check:
	$(UV_RUN) ruff format --check src/ tests/ examples/

lint:
	$(UV_RUN) ruff check src/ tests/ examples/

lint-fix:
	$(UV_RUN) ruff check --fix src/ tests/ examples/

test:
	$(UV_RUN) pytest -q

test-unit:
	$(UV_RUN) pytest -q tests/test_agent_runtime_fake.py tests/test_projection.py tests/test_api_responses.py

test-sdk:
	$(UV_RUN) pytest -q tests/test_openai_sdk_compat.py

check: format-check lint test

run serve:
	FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

run-nano:
	FLOWJET_BACKEND=nano FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

examples:
	@echo "Start a real agent in another terminal:  make sync-nano && make run-nano"
	@echo "(Use make run only for deterministic fake/Echo demos.)"
	@echo "Then:"
	@echo "  make examples-sdk     # OpenAI SDK end-to-end"
	@echo "  make examples-http    # Raw HTTP end-to-end"
	@echo "  make examples-e2e     # both"
	@echo "See examples/README.md"

examples-sdk:
	$(UV_RUN) python examples/e2e_openai_sdk.py

examples-http:
	$(UV_RUN) python examples/e2e_http_api.py

examples-e2e: examples-sdk examples-http

build:
	rm -rf dist/
	uv build

clean:
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/ .mypy_cache/ htmlcov/ coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
