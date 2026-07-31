# FlowJet Server

OpenAI Responses–compatible HTTP service over **soothe-nano**, with thread-pool isolation. Protocol adapter: clients speak the OpenAI Responses API; the server projects Agent Runtime events onto that surface.

## Specs

- [RFC-001](docs/specs/RFC-001-openai-compatible-api.md)
- [RFC-002](docs/specs/RFC-002-isolated-thread-pool-runtime.md) — thread-pool isolation
- [IG-001](docs/impl/IG-001-openai-compatible-server.md)
- [IG-002](docs/impl/IG-002-isolated-thread-pool-runtime.md)

## Quick start

```bash
make sync-dev
make run
```

In another terminal, run the end-to-end API examples:

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
| `FLOWJET_MODELS` | `default` | Comma-separated logical model ids |
| `FLOWJET_HOST` | `0.0.0.0` | Bind host |
| `FLOWJET_PORT` | `8080` | Bind port |
| `FLOWJET_HOME` | `~/.flowjet` | Root for per-session workspaces |
| `FLOWJET_NANO_CONFIG` | unset | Optional path to nano.yml (else `$SOOTHE_HOME/config/nano.yml`) |
| `FLOWJET_THREAD_POOL_MIN` | `2` | Min isolation worker threads |
| `FLOWJET_THREAD_POOL_MAX` | `8` | Max isolation worker threads |
| `FLOWJET_REUSE_RUNNER` | `true` | Reuse agent adapter per worker |
| `FLOWJET_REQUEST_TIMEOUT` | `0` | Per-run timeout seconds (`0` = none) |

## License

MIT
