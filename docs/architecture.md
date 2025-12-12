# Architecture Overview

This project follows a four-layer stack tailored for NL2SQL:

1) **API / UI (接入层)**  
   - Receives natural language questions plus session/user metadata.  
   - Validates permissions/read-only flags, builds a `QueryRequest`.  
   - Can be REST/gRPC/queue consumer; here we keep a lightweight handler stub.

2) **Orchestrator (编排层)**  
   - Creates and maintains `QueryContext`.  
   - Calls `Router → SchemaAgent → SQLGenerator → Verifier/Executor` with retry/stop conditions.  
   - Persists full context for auditing and evaluation.

3) **Agents (业务 LLM 逻辑层)**  
   - **Router**: picks candidate DBs and a high-level plan based on a compact catalog + session summary.  
   - **SchemaAgent (AutoLink-style)**: iteratively retrieves schema snippets through tools; maintains `linked_schema` and `linking_trace`.  
   - **SQLGenerator**: produces SQL candidates using the trimmed schema + doc snippets.  
   - **Verifier/Executor**: probes SQL, summarizes results/errors, selects final decision.

4) **Infra / Tools (基础设施层)**  
   - **SchemaVectorStoreService**: column-level embeddings and search.  
   - **DBIntrospectionService**: read-only probe with whitelist templates and row/time guards.  
- **LLM Gateway**: routes to DeepSeek/Qwen/GPT/etc.  
- **Storage/Telemetry**: saves `QueryContext`, metrics, logs.

Spider2-snow integration:
- `SpiderSnowSchemaStore` reads DB_schema JSON/DDL directly from `Spider2/spider2-snow/resource/databases`.
- `SpiderSnowDBIntrospectionService` returns sample rows from those JSON files for probe/verify steps.
- `SnowflakeProbeService` can run online read-only SELECT probes against Snowflake using the `snowflake_credential.json` format from spider-agent-snow (enable via env `SPIDER_SNOW_MODE=online` and `SNOWFLAKE_CRED_PATH`).
- Set `SPIDER_SNOW_BASE` env var to override the default path lookup.

## Data Contracts
- **QueryRequest**: user/session/query/options.  
- **QueryContext**: carries router/schema/retrieval/sql_generation/execution/final_decision + metrics.  
- **SchemaAgentState**: internal linked schema, retrieve cache, seen columns, trace, step counter.

## Flow Summary
1. API builds `QueryRequest`.  
2. Orchestrator seeds `QueryContext` and delegates to agents.  
3. Router writes `router.*`; SchemaAgent writes `schema_state.*`; SQLGenerator writes `sql_generation_state.*`; Verifier writes `execution_state` + `final_decision`.  
4. Orchestrator returns a trimmed response and persists full context.

## Extending
- Swap the stub LLM client with your gateway; keep the `LLMClient.chat` signature.  
- Replace `SchemaVectorStoreService` and `DBIntrospectionService` with real implementations.  
- Add doc retrieval in `retrieval_state` if you need business dictionary grounding.  
- Wire a REST server by importing `Orchestrator` in `src/api/handler.py`.
