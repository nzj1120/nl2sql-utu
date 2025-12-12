"""
Router agent selects a database and emits a coarse plan.
"""

from typing import Any, Dict, List

from src.infra.llm import LLMClient


class RouterAgent:
    """
    Lightweight planner that chooses a target database and hints for downstream agents.
    """

    name = "router"

    def __init__(self, llm: LLMClient):
        """
        Create a RouterAgent with an LLM client.
        """
        self.llm = llm

    def route(self, user_query: str, db_catalog: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Produce candidate dbs, a chosen db, and a high-level plan.
        """
        candidates = list(db_catalog.keys())
        chosen_db = self._select_db(user_query, db_catalog, candidates)
        plan = self._draft_plan(user_query, db_catalog.get(chosen_db, {}))
        return {
            "candidate_dbs": candidates,
            "chosen_db": chosen_db,
            "high_level_plan": plan,
        }

    def _select_db(self, user_query: str, db_catalog: Dict[str, Dict[str, Any]], candidates: List[str]) -> str:
        """
        Select a database by simple heuristic or LLM scoring.
        """
        if not candidates:
            return ""
        # Simple heuristic: pick the db whose description shares the most keywords; fall back to first.
        lower_query = user_query.lower()
        scores = []
        for db_id in candidates:
            desc = db_catalog.get(db_id, {}).get("short_desc", "").lower()
            overlap = sum(1 for token in lower_query.split() if token in desc)
            scores.append((overlap, db_id))
        scores.sort(reverse=True)
        best = scores[0][1]
        return best

    def _draft_plan(self, user_query: str, db_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a small plan with task type guess and hinted tables.
        """
        hint_tables = db_meta.get("example_tables", [])[:3]
        return {
            "task_type": "aggregation" if "sum" in user_query.lower() or "总" in user_query else "lookup",
            "hint_tables": hint_tables,
        }
