"""
Schema agent implementing an AutoLink-style iterative schema linking loop.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import json

from src.core.context import QueryContext
from src.infra.llm import LLMClient
from src.infra.vector_store import SchemaVectorStoreService, ColumnSnippet
from src.infra.db import DBIntrospectionService, ProbeResult


@dataclass
class SchemaAgentConfig:
    """
    Tunable parameters for the schema agent.
    """

    initial_top_m: int = 80
    retrieve_top_k: int = 5
    max_steps: int = 8
    prompt_token_budget: int = 4000
    min_feedback_actions_per_step: int = 1
    enable_verify_schema: bool = True
    enable_explore_schema: bool = True


@dataclass
class TableSchema:
    """
    Compact table schema representation.
    """

    table: str
    columns: List[ColumnSnippet] = field(default_factory=list)


@dataclass
class TraceStep:
    """
    Single step record capturing LLM actions and tool observations.
    """

    step: int
    llm_actions: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    forced_stop: bool = False


@dataclass
class SchemaAgentState:
    """
    Working state for the schema agent across iterations.
    """

    db_id: str
    user_query: str
    table_list: List[str]
    linked_schema: Dict[str, TableSchema]
    seen_columns: Set[str]
    retrieve_cache: Dict[str, List[ColumnSnippet]]
    trace: List[TraceStep]
    step: int = 0


def build_schema_from_columns(columns: List[ColumnSnippet]) -> Dict[str, TableSchema]:
    """
    Group column snippets into a table→TableSchema mapping.
    """
    tables: Dict[str, TableSchema] = {}
    for col in columns:
        table_schema = tables.setdefault(col.table, TableSchema(table=col.table))
        table_schema.columns.append(col)
    return tables


class SchemaAgent:
    """
    AutoLink-style schema agent that alternates LLM planning and tool feedback.
    """

    name = "schema_agent"

    def __init__(
        self,
        llm: LLMClient,
        vector_store: SchemaVectorStoreService,
        db_service: DBIntrospectionService,
        config: Optional[SchemaAgentConfig] = None,
    ):
        """
        Create a schema agent with its tool dependencies.
        """
        self.llm = llm
        self.vector_store = vector_store
        self.db_service = db_service
        self.config = config or SchemaAgentConfig()

    def run(self, user_query: str, db_id: str, table_list: List[str], ctx: QueryContext) -> QueryContext:
        """
        Execute the schema linking workflow and write results back into context.
        """
        initial_cols = self.vector_store.search_columns(db_id=db_id, query=user_query, exclude_cols=[], top_k=self.config.initial_top_m)
        state = SchemaAgentState(
            db_id=db_id,
            user_query=user_query,
            table_list=table_list,
            linked_schema=build_schema_from_columns(initial_cols),
            seen_columns={col.id for col in initial_cols},
            retrieve_cache={},
            trace=[],
        )
        ctx.schema_state = {
            "table_list": table_list,
            "linked_schema": self._serialize_linked_schema(state.linked_schema),
        }

        while state.step < self.config.max_steps:
            prompt = self._build_prompt(state)
            actions = self._call_llm(prompt)
            observations: List[Dict[str, Any]] = []

            feedback_actions = 0
            for action in actions:
                obs = self._dispatch_action(action, state)
                if obs is not None:
                    observations.append(obs)
                if action["type"] in {"retrieve_schema", "explore_schema", "verify_schema"}:
                    feedback_actions += 1

            if feedback_actions < self.config.min_feedback_actions_per_step:
                observations.append({"warning": "no_feedback_action", "detail": "Add retrieve_schema/explore_schema/verify_schema"})

            state.trace.append(TraceStep(step=state.step, llm_actions=actions, observations=observations))
            ctx.schema_state["linking_trace"] = self._serialize_trace(state.trace)
            ctx.schema_state["linked_schema"] = self._serialize_linked_schema(state.linked_schema)

            if any(action["type"] == "stop_action" for action in actions):
                break

            state.step += 1

        if state.step >= self.config.max_steps and state.trace:
            state.trace[-1].forced_stop = True  # mark last step
        return ctx

    def _dispatch_action(self, action: Dict[str, Any], state: SchemaAgentState) -> Optional[Dict[str, Any]]:
        """
        Execute a single action and return an observation.
        """
        action_type = action.get("type")
        if action_type == "retrieve_schema":
            query = action.get("query", state.user_query)
            top_k = int(action.get("top_k", self.config.retrieve_top_k))
            cols = self.vector_store.search_columns(
                db_id=state.db_id,
                query=query,
                exclude_cols=list(state.seen_columns),
                top_k=top_k,
            )
            cache_key = f"step-{state.step}-{len(state.retrieve_cache)}"
            state.retrieve_cache[cache_key] = cols
            return {"action": "retrieve_schema", "query": query, "returned": [c.id for c in cols]}

        if action_type == "explore_schema" and self.config.enable_explore_schema:
            sql = action.get("sql", "")
            probe = self.db_service.exec_probe(db_id=state.db_id, sql=sql)
            return {"action": "explore_schema", "status": probe.status, "summary": probe.summary}

        if action_type == "verify_schema" and self.config.enable_verify_schema:
            sql = action.get("sql", "")
            probe = self.db_service.exec_probe(db_id=state.db_id, sql=sql)
            return {"action": "verify_schema", "status": probe.status, "error": probe.error_type, "message": probe.error_message_short}

        if action_type == "add_schema":
            cols_to_add = self._resolve_columns(action.get("columns", []), state)
            state.linked_schema = self._merge_schema(state.linked_schema, cols_to_add)
            for col in cols_to_add:
                state.seen_columns.add(col.id)
            return {"action": "add_schema", "added": [c.id for c in cols_to_add]}

        if action_type == "stop_action":
            return {"action": "stop_action"}

        return {"action": "unknown", "detail": action}

    def _resolve_columns(self, col_names: List[str], state: SchemaAgentState) -> List[ColumnSnippet]:
        """
        Resolve column identifiers from cache or vector store fallback.
        """
        resolved: List[ColumnSnippet] = []
        cache_values = [c for cols in state.retrieve_cache.values() for c in cols]
        cache_index = {c.id: c for c in cache_values}
        for col_name in col_names:
            if col_name in cache_index:
                resolved.append(cache_index[col_name])
                continue
            table, _, column = col_name.partition(".")
            fetched = self.vector_store.search_columns(state.db_id, query=f"{table} {column}", exclude_cols=list(state.seen_columns), top_k=1)
            if fetched:
                resolved.append(fetched[0])
        return resolved

    def _merge_schema(self, linked_schema: Dict[str, TableSchema], cols_to_add: List[ColumnSnippet]) -> Dict[str, TableSchema]:
        """
        Merge new columns into the linked schema dictionary.
        """
        for col in cols_to_add:
            table_schema = linked_schema.setdefault(col.table, TableSchema(table=col.table))
            existing_cols = {c.id: c for c in table_schema.columns}
            if col.id not in existing_cols:
                table_schema.columns.append(col)
        return linked_schema

    def _build_prompt(self, state: SchemaAgentState) -> str:
        """
        Construct the LLM prompt summarizing current state and action schema.
        """
        schema_summary = "; ".join(
            f"{t.table}: " + ", ".join(f"{c.name}:{c.type}" for c in t.columns[:5])
            for t in state.linked_schema.values()
        )
        trace_tail = state.trace[-2:]
        trace_text = "\n".join(f"step {t.step}: actions={t.llm_actions}, observations={t.observations}" for t in trace_tail)
        prompt = f"""
You are a schema linking agent. Goal: maximize recall with minimal columns.
User query: {state.user_query}
Database: {state.db_id}
Tables: {", ".join(state.table_list)}
Current linked schema (truncated): {schema_summary}
Recent trace: {trace_text}
Output ONLY JSON array of actions with fields: type, query/top_k/sql/columns as needed.
Allowed actions: retrieve_schema, explore_schema, verify_schema, add_schema, stop_action.
Ensure at least one feedback action per step.
"""
        return prompt.strip()

    def _call_llm(self, prompt: str) -> List[Dict[str, Any]]:
        """
        Call the LLM and parse the JSON action list. Fall back to stop when parsing fails.
        """
        raw = self.llm.chat(prompt=prompt)
        try:
            actions = json.loads(raw)
            if isinstance(actions, list):
                return actions
        except Exception:
            pass
        return [{"type": "stop_action"}]

    def _serialize_linked_schema(self, linked_schema: Dict[str, TableSchema]) -> Dict[str, Any]:
        """
        Convert TableSchema objects to plain dicts for the context.
        """
        out: Dict[str, Any] = {}
        for table, schema in linked_schema.items():
            out[table] = {
                "columns": [
                    {
                        "name": c.name,
                        "type": c.type,
                        "role": "pk" if c.is_pk else ("fk" if c.is_fk else "col"),
                        "description": c.description,
                        "sample_values": c.sample_values[:3],
                    }
                    for c in schema.columns
                ]
            }
        return out

    def _serialize_trace(self, trace: List[TraceStep]) -> List[Dict[str, Any]]:
        """
        Convert TraceStep objects to dicts for the context.
        """
        return [
            {
                "step": t.step,
                "llm_actions": t.llm_actions,
                "observations": t.observations,
                "forced_stop": t.forced_stop,
            }
            for t in trace
        ]
