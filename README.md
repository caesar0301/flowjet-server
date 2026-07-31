# FlowJet Server

OpenAI Responses–compatible HTTP service. Protocol adapter over pluggable agent runtimes (Phase 1: fake backend + optional soothe-nano bridge).

## Specs

- [RFC-001](docs/specs/RFC-001-openai-compatible-api.md)
- [IG-001](docs/impl/IG-001-openai-compatible-server.md)

## Quick start

```bash
make sync-dev
make run
```

This starts the deterministic fake backend. To use the real soothe-nano agent:

```bash
make sync-nano
make run-nano
```

In another terminal, run the end-to-end API examples against either server:

```bash
make examples-sdk    # OpenAI Python SDK walkthrough
make examples-http   # Raw HTTP (health + all /v1 endpoints + SSE)
# or: make examples-e2e
```

See [examples/README.md](examples/README.md).

```python
from openai import OpenAI

client = OpenAI(api_key="local", base_url="http://127.0.0.1:8080/v1")
print(client.responses.create(model="default", input="Hello"))
```

Useful Make targets: `make help`, `make test`, `make test-sdk`, `make check`, `make lint`.

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `FLOWJET_API_KEY` | unset | If set, require Bearer auth |
| `FLOWJET_BACKEND` | `fake` | `fake` or `nano` |
| `FLOWJET_MODELS` | `default` | Comma-separated logical model ids |
| `FLOWJET_HOST` | `0.0.0.0` | Bind host |
| `FLOWJET_PORT` | `8080` | Bind port |

## License

MIT
