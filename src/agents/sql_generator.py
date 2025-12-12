"""
SQL generator agent that turns linked schema and query into candidate SQL.
"""

from typing import Any, Dict, List

from src.core.context import QueryContext
from src.infra.llm import LLMClient


class SQLGeneratorAgent:
    """
    Produces SQL candidates using a trimmed schema and optional doc snippets.
    """

    name = "sql_generator"

    def __init__(self, llm: LLMClient, max_candidates: int = 2):
        """
        Create a SQL generator with an LLM client.
        """
        self.llm = llm
        self.max_candidates = max_candidates

    def generate(self, ctx: QueryContext) -> Dict[str, Any]:
        """
        Generate one or more SQL candidates and return a state dict.
        """
        prompt = self._build_prompt(ctx)
        raw = self.llm.chat(prompt=prompt)
        # Expect lines of SQL; split safely.
        candidates = [line.strip() for line in raw.splitlines() if line.strip()][: self.max_candidates]
        if not candidates:
            candidates = ["SELECT 1;"]
        return {"candidates": candidates}

    def _build_prompt(self, ctx: QueryContext) -> str:
        """
        Compose an LLM prompt with the linked schema subset.
        """
        schema_text = []
        for table, meta in ctx.schema_state.get("linked_schema", {}).items():
            columns = meta.get("columns", [])
            col_text = ", ".join(f"{c['name']} {c.get('type', '')}" for c in columns[:10])
            schema_text.append(f"{table}({col_text})")
        schema_line = "; ".join(schema_text)
        return (
            "You are an SQL generator for NL2SQL.\n"
            f"Question: {ctx.user_query}\n"
            f"Schema subset: {schema_line}\n"
            "Generate executable SQL; keep it concise. Provide one SQL per line."
        )
