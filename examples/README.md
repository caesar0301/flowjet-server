# FlowJet Server examples

User-facing scripts that talk to **flowjet-server** with the official OpenAI Python SDK.
Only `base_url` (and optionally `api_key`) change — the Responses API calls are stock OpenAI.

## Prerequisites

Terminal 1 — start the server (fake backend is enough for demos):

```bash
cd /path/to/flowjet-server
uv sync --extra dev
uv run flowjet-server
```

Server listens on `http://127.0.0.1:8080` by default (`/v1` for the SDK).

Terminal 2 — run an example:

```bash
uv run python examples/01_create_response.py
uv run python examples/02_stream_response.py
uv run python examples/03_models_retrieve_delete.py
uv run python examples/04_flowjet_progress.py
uv run python examples/05_flowjet_developer.py
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FLOWJET_BASE_URL` | `http://127.0.0.1:8080/v1` | OpenAI SDK `base_url` |
| `FLOWJET_API_KEY` / `OPENAI_API_KEY` | `local` | Bearer token (any value if server auth is off) |

If the server was started with `FLOWJET_API_KEY=secret`, use the same value in the client env.

## Scripts

| Script | What it shows |
|--------|----------------|
| `01_create_response.py` | Non-streaming `responses.create` |
| `02_stream_response.py` | Streaming tokens via `responses.stream` |
| `03_models_retrieve_delete.py` | `models.list`, retrieve, delete |
| `04_flowjet_progress.py` | FlowJet `progress` projection via `extra_body` |
| `05_flowjet_developer.py` | FlowJet `developer` projection (tool summaries) |
