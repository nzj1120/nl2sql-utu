# Code Review

## Overview
The NL2SQL YouTu Agent repository provides a multi-agent skeleton for routing NL queries to SQL generation through router, schema-linking, SQL generation, and verification stages. The architecture is intentionally modular with stubbed infra to swap in production implementations.

## Strengths
- Clear orchestration path from request to response with explicit context propagation and persistence hooks, making the data flow easy to follow and extend.
- Agents and infra services are defined behind small interfaces (LLM, vector store, DB introspection), reducing coupling and simplifying substitution during integration.

## Findings
### Failing test harness (blocking)
- `pytest` cannot import the `src` package (`ModuleNotFoundError`) because the repository is not installed as a package nor is the path added for tests. Tests currently fail on collection, masking downstream regressions.
  - Evidence: `pytest -q` fails to import `src.main` during `tests/test_pipeline_smoke.py` collection with `ModuleNotFoundError: No module named 'src'`.【7752ad†L1-L14】

### No guard when router returns no database (major)
- `Orchestrator.run` unconditionally passes `chosen_db` into the schema agent and verifier. When routing yields `None` or an empty string, the downstream agents still execute searches and probes with that identifier, producing low-signal traces and hiding the real routing failure instead of surfacing a clear error to the caller.
  - `chosen_db` is read directly from the router output and then used to fetch tables and drive the schema run without validation.【F:src/core/pipeline.py†L43-L70】
  - The schema agent immediately searches the vector store with the provided `db_id`, even if it is empty, which would return an empty linked schema and continue the loop with misleading state.【F:src/agents/schema.py†L101-L147】

### Verifier action dispatch executes arbitrary SQL without safety rails (major)
- The schema agent’s `_dispatch_action` hands LLM-produced SQL directly to `DBIntrospectionService.exec_probe` for both `explore_schema` and `verify_schema` actions without sanitization or readonly enforcement. In a real backend, this risks unsafe probes or heavy queries initiated by the model.
  - LLM actions flow into `exec_probe` calls via `explore_schema` and `verify_schema` branches without checks on allowed verbs, rate limits, or budget enforcement.【F:src/agents/schema.py†L149-L186】

### SQL generation fallback produces placeholder output (minor)
- When the LLM response cannot be parsed, the SQL generator falls back to a hardcoded `SELECT 1;`. This placeholder can mask upstream failures and may be propagated as a successful verification if the stub DB accepts it, hiding issues with prompt construction or model availability.
  - The generator splits raw LLM output into candidates and defaults to `SELECT 1;` when empty.【F:src/agents/sql_generator.py†L25-L35】

## Recommendations
- Add a test entry point that ensures `src` is importable (e.g., installing the package in editable mode or adjusting `PYTHONPATH` within test configuration) so the smoke test reflects real execution.
- Validate router output in `Orchestrator.run`; if no database is selected, short-circuit with a clear error response rather than running downstream agents with an empty `db_id`.
- Introduce guardrails for DB probe actions: enforce readonly SQL patterns, cap runtime/row limits, and consider explicit allowlists before dispatching LLM-produced statements to the database service.
- Replace the `SELECT 1;` fallback with an explicit error flag in the SQL generation state so verification can fail fast and surface LLM issues to observability/clients.
