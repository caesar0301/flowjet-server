# Makefile for flowjet-server
UV_RUN ?= uv run
HOST ?= 0.0.0.0
PORT ?= 8080

.PHONY: help sync sync-dev format format-check lint lint-fix \
	test test-sdk test-unit check run serve run-fake run-nano run-soothe examples \
	examples-sdk examples-http examples-e2e build clean

help:
	@echo "flowjet-server"
	@echo ""
	@echo "  make sync           - Sync runtime dependencies (includes soothe)"
	@echo "  make sync-dev       - Sync with dev extras (pytest, openai, ruff)"
	@echo "  make format         - Format with ruff"
	@echo "  make format-check   - Check formatting (CI)"
	@echo "  make lint           - Lint with ruff"
	@echo "  make lint-fix       - Auto-fix lint issues"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit/API tests (exclude live SDK suite)"
	@echo "  make test-sdk       - Run OpenAI SDK compatibility tests"
	@echo "  make check          - format-check + lint + test"
	@echo "  make run / serve    - Start with default nano backend (thread-pool)"
	@echo "  make run-fake       - Start with deterministic fake/Echo backend"
	@echo "  make run-nano       - Same as run (explicit FLOWJET_BACKEND=nano)"
	@echo "  make run-soothe     - Start with full SootheRunner"
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
	$(UV_RUN) pytest -q tests/test_agent_runtime_fake.py tests/test_projection.py \
		tests/test_api_responses.py tests/test_isolation.py

test-sdk:
	$(UV_RUN) pytest -q tests/test_openai_sdk_compat.py

check: format-check lint test

run serve:
	FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

run-fake:
	FLOWJET_BACKEND=fake FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

run-nano:
	FLOWJET_BACKEND=nano FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

run-soothe:
	FLOWJET_BACKEND=soothe FLOWJET_HOST=$(HOST) FLOWJET_PORT=$(PORT) $(UV_RUN) flowjet-server

examples:
	@echo "Start the server in another terminal:  make sync-dev && make run"
	@echo "(Or: make run-soothe / make run-fake. Default backend is nano.)"
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
