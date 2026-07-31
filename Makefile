# Makefile for flowjet-server
UV_RUN ?= uv run
HOST ?= 0.0.0.0
PORT ?= 8080

.PHONY: help sync sync-dev sync-nano format format-check lint lint-fix \
	test test-sdk test-unit check run serve examples \
	example-create example-stream build clean

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
	@echo "  make run / serve    - Start flowjet-server (HOST=$(HOST) PORT=$(PORT))"
	@echo "  make examples       - Print how to run OpenAI SDK examples"
	@echo "  make example-create - Run examples/01_create_response.py"
	@echo "  make example-stream - Run examples/02_stream_response.py"
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

examples:
	@echo "Start the server in another terminal:  make run"
	@echo "Then:"
	@echo "  make example-create"
	@echo "  make example-stream"
	@echo "  uv run python examples/03_models_retrieve_delete.py"
	@echo "  uv run python examples/04_flowjet_progress.py"
	@echo "  uv run python examples/05_flowjet_developer.py"
	@echo "See examples/README.md"

example-create:
	$(UV_RUN) python examples/01_create_response.py

example-stream:
	$(UV_RUN) python examples/02_stream_response.py

build:
	rm -rf dist/
	uv build

clean:
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/ .mypy_cache/ htmlcov/ coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
