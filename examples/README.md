# FlowJet Server examples

End-to-end demos of the **public API** against a running `flowjet-server`.

These replace the older numbered one-off scripts. Each script walks the full
surface you need as an app developer.

| Script | Client | Covers |
|--------|--------|--------|
| [`e2e_openai_sdk.py`](e2e_openai_sdk.py) | Official OpenAI Python SDK | `models.list`, create (string + list input), stream, retrieve, delete, FlowJet `report` / `progress` / `developer` via `extra_body`, error paths |
| [`e2e_http_api.py`](e2e_http_api.py) | Raw `httpx` | `GET /health`, all `/v1/*` endpoints, SSE wire format, `response.flowjet.*` events, OpenAI-style error JSON |

Shared helpers live in [`_client.py`](_client.py).

## Run against the server

Terminal 1 — sync deps and start soothe-nano:

```bash
make sync-dev
make run
```

Terminal 2 — run an end-to-end example:

```bash
make examples-sdk    # OpenAI SDK walkthrough
make examples-http   # Raw HTTP walkthrough
# or both:
make examples-e2e
```

The server uses soothe-nano with thread-pool isolation. Nano loads
`~/.soothe/config/nano.yml` (or `FLOWJET_NANO_CONFIG`) and its active router profile.

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FLOWJET_BASE_URL` | `http://127.0.0.1:8080/v1` | OpenAI SDK `base_url` |
| `FLOWJET_API_KEY` / `OPENAI_API_KEY` | `local` | Bearer token (any value if server auth is off) |

If the server was started with `FLOWJET_API_KEY=secret`, use the same value for the client.

## API map

| Step | HTTP | SDK |
|------|------|-----|
| Health | `GET /health` | _(httpx only)_ |
| List models | `GET /v1/models` | `client.models.list()` |
| Create | `POST /v1/responses` | `client.responses.create(...)` |
| Stream | `POST /v1/responses` + SSE | `client.responses.stream(...)` / `stream=True` |
| Retrieve | `GET /v1/responses/{id}` | `client.responses.retrieve(id)` |
| Delete | `DELETE /v1/responses/{id}` | `client.responses.delete(id)` |
| FlowJet options | body `flowjet` | `extra_body={"flowjet": {...}}` |
