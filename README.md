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

In another terminal, run the OpenAI SDK examples:

```bash
make example-create
make example-stream
# or: make examples   # lists all example commands
```

See [examples/README.md](examples/README.md) for the full set (streaming, retrieve/delete, FlowJet progress/developer projections).

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
