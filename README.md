# FlowJet Server

OpenAI Responses–compatible HTTP service backed by **[soothe-nano](https://github.com/mirasoth/soothe-nano)** (≥1.1.1). Clients use the official OpenAI SDK (or raw HTTP); FlowJet projects Agent Runtime events onto the Responses API, with optional namespaced extensions under `flowjet` / `response.flowjet.*`.

## Quick start (local)

```bash
make sync-dev
make run
```

In another terminal:

```bash
make examples-sdk    # OpenAI Python SDK walkthrough
make examples-http   # Raw HTTP (health + /v1 + SSE)
```

```python
from openai import OpenAI

client = OpenAI(api_key="local", base_url="http://127.0.0.1:8080/v1")
print(client.responses.create(model="default", input="Hello"))
```

Useful Make targets: `make help`, `make test`, `make test-sdk`, `make check`, `make lint`.

## Deploy

Self-contained Docker stack (PostgreSQL + pgvector + flowjet-server). Full details: [deploy/README.md](deploy/README.md).

```bash
cd deploy
cp env-example .env   # set DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL
docker compose up -d
curl http://127.0.0.1:8080/health
```

| Piece | Role |
|-------|------|
| `flowjet-pgvector` | Checkpoints, metadata, vectors, memory |
| `flowjet-server` | OpenAI Responses HTTP on port 8080 |

Nano config is mounted from `deploy/nano.yml` (DashScope + Postgres). The image also bakes a default under `/var/lib/soothe/config/nano.yml`.

## OpenAI protocol + FlowJet options

Base path: `/v1` (OpenAI SDK `base_url` should end with `/v1`).

| HTTP | SDK |
|------|-----|
| `GET /health` | — |
| `GET /v1/models` | `client.models.list()` |
| `POST /v1/responses` | `client.responses.create(...)` |
| `POST /v1/responses` + SSE | `client.responses.stream(...)` / `stream=True` |
| `GET /v1/responses/{id}` | `client.responses.retrieve(id)` |
| `DELETE /v1/responses/{id}` | `client.responses.delete(id)` |

### Standard create

```python
client.responses.create(model="default", input="Summarize the repo layout.")
```

### FlowJet custom arguments (`extra_body.flowjet`)

Pass FlowJet fields via OpenAI SDK `extra_body` (or the same JSON object on raw HTTP):

```python
client.responses.create(
    model="default",
    input="What does create_nano_agent do?",
    extra_body={
        "flowjet": {
            "projection": "progress",          # report | progress | developer
            "session": "fj-my-app-session",    # stable LangGraph thread / workspace key
            "interaction_mode": "ask",         # agent (default) | ask
            "metadata": {"app": "demo"},       # opaque; forwarded to the runtime
        }
    },
)
```

| Field | Values | Default | Meaning |
|-------|--------|---------|---------|
| `projection` | `report` \| `progress` \| `developer` | `report` | How much SSE/detail to expose |
| `session` | string | new `fj-<uuid>` | Isolates workspace + conversation thread |
| `interaction_mode` | `agent` \| `ask` | `agent` | soothe-nano mode (see below) |
| `metadata` | object | — | Opaque bag (e.g. `workspace` override path) |

**Projection modes**

- **`report`** — final answer only (OpenAI lifecycle events).
- **`progress`** — plus `response.flowjet.progress` stages (no CoT / tool args).
- **`developer`** — plus `response.flowjet.tool.started` / `.completed` summaries (still no tool arguments).

**Ask vs Agent (`interaction_mode`)**

Requires **soothe-nano ≥ 1.1.1**. The server builds a `DualModeCoreAgent` and routes each request by `flowjet.interaction_mode`:

| Mode | Behavior |
|------|----------|
| `agent` | Full coding agent: read/write tools, shell/`file_ops` when enabled in nano.yml |
| `ask` | Hard read-only: inspect with `ls` / `read_file` / `glob` / `grep` / `file_info`; no writes or shell |

Mode is pinned per `session` (thread). To switch modes, use a **new** `session` (or a fresh client conversation id).

Streaming example with Ask + progress:

```python
with client.responses.stream(
    model="default",
    input="Explain how auth works in this workspace.",
    extra_body={
        "flowjet": {
            "projection": "progress",
            "session": "fj-ask-docs",
            "interaction_mode": "ask",
        }
    },
) as stream:
    for event in stream:
        if event.type == "response.flowjet.progress":
            print(event.stage, event.message)
        elif event.type == "response.output_text.delta":
            print(event.delta, end="", flush=True)
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FLOWJET_API_KEY` | unset | If set, require Bearer auth |
| `FLOWJET_MODELS` | `default` | Comma-separated logical model ids |
| `FLOWJET_HOST` | `0.0.0.0` | Bind host |
| `FLOWJET_PORT` | `8080` | Bind port |
| `FLOWJET_HOME` | `~/.flowjet` | Root for per-session workspaces |
| `FLOWJET_NANO_CONFIG` | unset | Optional nano.yml (else `$SOOTHE_HOME/config/nano.yml`) |
| `FLOWJET_THREAD_POOL_MIN` | `2` | Min isolation worker threads |
| `FLOWJET_THREAD_POOL_MAX` | `8` | Max isolation worker threads |
| `FLOWJET_REUSE_RUNNER` | `true` | Reuse agent adapter per worker |
| `FLOWJET_REQUEST_TIMEOUT` | `0` | Per-run timeout seconds (`0` = none) |

FlowJet always forces nano's `security.allow_paths_outside_workspace` to `false`, even if the loaded nano.yml requests otherwise.

## License

MIT
