# Changelog

All notable changes to **flowjet-server** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] — 2026-09-05

### Fixed

- **litellm corrupted-install fix.** The previous image (v0.1.0) shipped a
  broken `litellm` 1.99.0 wheel: `litellm/__init__.py` was listed in the
  dist-info RECORD but missing from disk, so Python treated the package as an
  empty namespace package and every `/v1/responses` call failed with
  `module 'litellm' has no attribute 'acompletion'`. Reinstalling litellm with
  `uv pip install --force-reinstall litellm==1.99.0` restores
  `litellm/__init__.py` and `acompletion` becomes available again. The Docker
  image now rebuilds the venv cleanly so the fix is baked into the published
  image.

### Verified

Full E2E suite (`examples/e2e_http_api.py`) passes against the live server:

| Endpoint | Method | Result |
|---|---|---|
| `/health` | GET | ✅ `{"status":"ok",...}` |
| `/v1/models` | GET | ✅ returns `default` model |
| `/v1/responses` (stream=false) | POST | ✅ status `completed`, real LLM text |
| `/v1/responses/{id}` | GET | ✅ retrieve returns stored response |
| `/v1/responses/{id}` | DELETE | ✅ `deleted:true`, subsequent GET → 404 |
| `/v1/responses` (SSE, report) | POST | ✅ `response.created` → `output_text.delta` → `response.completed` |
| `/v1/responses` (SSE, progress) | POST | ✅ includes `response.flowjet.progress` stages |
| `/v1/responses` (SSE, developer) | POST | ✅ completes; no tool args leaked to wire |
| unknown model | POST | ✅ HTTP 404 `model_not_found` |
| missing id | GET | ✅ HTTP 404 `response_not_found` |

## [0.1.0] — initial release

OpenAI Responses–compatible HTTP service backed by soothe-nano (≥1.2.23).
Includes ask/agent interaction modes, three SSE projection modes
(report / progress / developer), thread-pool isolation (RFC-002), production
isolation suite (RFC-003), and a self-contained Docker deploy stack
(PostgreSQL + pgvector + flowjet-server).

[0.1.1]: https://github.com/caesar0301/flowjet-server/releases/tag/v0.1.1
[0.1.0]: https://github.com/caesar0301/flowjet-server/releases/tag/v0.1.0
