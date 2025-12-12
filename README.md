# NL2SQL YouTu Agent

Standalone NL2SQL multi‑agent skeleton built for the YouTu framework and inspired by the Spider2 `spider-agent-snow` schema linking flow. The project focuses on a clear pipeline: **API → Orchestrator → Agents (Router / Schema / SQL Generator / Verifier) → Infra services**.

## Quick Start

1) Install deps (editable install is optional):
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2) Run the minimal CLI demo:
```bash
python -m src.main --query "上个月美国客户的订单金额总和是多少？"
```

3) Wire your own services:
- Set vector store / DB connection in `configs/config.example.yaml`.
- Add LLM keys via env vars (see `docs/architecture.md`).
- To test Spider2-snow data locally, ensure `Spider2/spider2-snow/resource/databases` exists or set `SPIDER_SNOW_BASE` to that folder; the schema store and probe services will read JSON/DDL directly.
- To probe online Snowflake data (参考 spider-agent-snow): set `SPIDER_SNOW_MODE=online` and `SNOWFLAKE_CRED_PATH` pointing to a `snowflake_credential.json` (same format as spider-agent-snow). Only SELECT probes are allowed and row limits are enforced.

## Layout
- `src/api`: Request/response objects and entry handlers (API/UI layer).
- `src/core`: QueryContext definition and orchestrator workflow.
- `src/agents`: Router, Schema (AutoLink-style), SQL generator, Verifier modules.
- `src/infra`: LLM gateway, vector store + DB introspection stubs, storage/telemetry hooks.
- `src/prompts`: Prompt templates (schema agent system prompt, etc.).
- `configs`: Example runtime configuration.
- `docs`: Architecture and module guides.
- `tests`: Smoke tests and placeholders.

## Notes
- All functions contain docstrings for fast onboarding.
- The schema agent follows an AutoLink-style action loop with `retrieve_schema`, `explore_schema`, `verify_schema`, `add_schema`, `stop_action`.
- This repo avoids heavy external dependencies; swap the stub services with real ones when connecting to your infra.
