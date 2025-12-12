# Schema Agent (AutoLink-style)

## Goal
Given a chosen `db_id` and a question, return a high-recall but compact `linked_schema` for SQL generation. Do this in bounded LLM/tool calls.

## Inputs / Outputs
- **Inputs**: `user_query`, `db_id`, `table_list`, current `linked_schema` summary, last trace summaries.
- **Outputs**: `schema_state.linked_schema`, `schema_state.linking_trace` updated inside `QueryContext`.

## Actions
- `retrieve_schema`: search vector store with `query`, `top_k`, `exclude_cols`.
- `explore_schema`: run whitelisted probe SQL via DB introspection.
- `verify_schema`: run candidate SQL to surface missing columns/tables.
- `add_schema`: merge observed columns into `linked_schema`.
- `stop_action`: terminate once coverage is sufficient.

## Workflow
1. **Initial retrieval**: one coarse VS search (`initial_top_m`) to seed `linked_schema`.  
2. **Iterative exploration**: per step, LLM proposes actions; tool calls feed observations; trace is recorded.  
3. **Termination**: stop when `stop_action` is issued or `max_steps` reached (forced stop flag).

## Prompt Hints
- System prompt states the role, budget, tools, and JSON-only output.  
- Per-step prompt includes user question, table names, compact linked schema, last 1–2 trace summaries, and JSON schema reminder.

## Error Handling
- Tool errors become observations so the next step can adjust queries.  
- Invalid actions are rejected with feedback; after repeated failures the agent stops conservatively with current schema.

## Config
See `SchemaAgentConfig` for knobs: `initial_top_m`, `retrieve_top_k`, `max_steps`, `prompt_token_budget`, `min_feedback_actions_per_step`, `enable_verify_schema`, `enable_explore_schema`.
