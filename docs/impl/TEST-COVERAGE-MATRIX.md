# flowjet-server Test Coverage Matrix

Attachment to [IG-003](IG-003-production-isolation-hardening.md) / RFC-001–003.
Maps product features → automated tests. Run with `make test` (or targets below).

---

## How to run

| Target | Scope |
|--------|--------|
| `make test` | Full suite |
| `make test-unit` | Fast unit + API (no live uvicorn SDK suite) |
| `make test-sdk` | OpenAI SDK against live uvicorn + FakeRuntimeBackend |
| `make test-concurrent` | Parallel HTTP/SSE load |
| `make test-features` | Comprehensive server feature ASGI suite |
| `make test-production` | RFC-003 production isolation suite |

---

## RFC-001 — OpenAI surface & projection

| Feature | Tests |
|---------|--------|
| `GET /health` | `test_api_responses`, `test_server_features` |
| `GET /v1/models` | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Create non-stream | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Create stream (SSE) | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Retrieve / delete | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Bearer auth | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Unknown model 404 | `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Projection `report` | `test_projection`, `test_openai_sdk_compat`, `test_server_features` |
| Projection `progress` | `test_projection`, `test_api_responses`, `test_openai_sdk_compat`, `test_server_features` |
| Projection `developer` | `test_projection`, `test_openai_sdk_compat`, `test_server_features` |
| List / message input | `test_openai_sdk_compat`, `test_server_features` |
| `flowjet` extra_body | `test_openai_sdk_compat`, `test_server_features` |
| Fake runtime event order | `test_agent_runtime_fake` |

---

## RFC-002 — Isolation

| Feature | Tests |
|---------|--------|
| Workspace hash vs override | `test_isolation`, `test_production_isolation` |
| Session admission serialize | `test_isolation` |
| Thread pool submit / cancel | `test_isolation` |
| Fresh ContextVar per turn | `test_isolation`, `test_production_isolation` (orphan) |
| Cross-session parallel FS | `test_isolation`, `test_server_features` |
| Same-session serialize | `test_isolation`, `test_server_features` |
| Disconnect before reuse | `test_isolation` |
| Isolating backend HTTP | `test_isolation`, `test_server_features` |
| Concurrent unique ids / SSE | `test_concurrent` |

---

## RFC-003 — Production hardening

| Feature | Tests |
|---------|--------|
| Control-frame delivery under backpressure | `test_production_isolation::test_control_frames_*` |
| Event drop counter | `test_production_isolation::test_backpressure_increments_events_dropped` |
| Scaled idle shrink | `test_production_isolation::test_scaled_worker_idles_out` |
| Max-requests recycle | `test_production_isolation::test_max_requests_recycles_baseline` |
| Ready timeout recycle | `test_production_isolation::test_ready_timeout_marks_worker_dead` |
| Request timeout | `test_production_isolation::test_request_timeout_yields_worker_error` |
| Cancel session | `test_production_isolation::test_cancel_session_cancels_in_flight` |
| Dead-worker watchdog respawn | `test_production_isolation::test_dead_worker_respawned_by_watchdog` |
| Orphan task cleanup | `test_production_isolation::test_orphan_tasks_cancelled_between_turns` |
| External workspace reject | `test_production_isolation`, `test_server_features` |
| Interaction mode pin | `test_production_isolation`, `test_server_features` |
| Settings knobs | `test_production_isolation::test_settings_pool_settings_*` |
| `/health` pool metrics | `test_production_isolation`, `test_server_features` |

---

## Nano bridge

| Feature | Tests |
|---------|--------|
| Progress / tool mapping | `test_nano_bridge` |
| Force workspace boundary | `test_nano_bridge` |
| Ask mode configurable | `test_nano_bridge` |
| Ask vs Agent e2e (live nano) | `make examples-modes` → `examples/e2e_ask_agent_modes.py` |
| Taint / recycle on fail/cancel | `test_nano_bridge` |

---

## Gaps (not automated here)

* Live LLM / soothe-nano end-to-end (use `make examples-sdk` / `examples-http`)
* Subprocess / Ray isolation (explicit RFC-003 non-goal)
* Multi-process Response store
