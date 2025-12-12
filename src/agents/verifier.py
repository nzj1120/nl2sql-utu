"""
Verifier agent that probes candidate SQL and chooses a final decision.
"""

from typing import Any, Dict, List, Tuple

from src.core.context import QueryContext
from src.infra.db import DBIntrospectionService, ProbeResult


class VerifierAgent:
    """
    Executes candidate SQL in probe mode and selects the final response.
    """

    name = "verifier"

    def __init__(self, db_service: DBIntrospectionService, max_rows: int = 5):
        """
        Create a verifier using the provided DB introspection service.
        """
        self.db_service = db_service
        self.max_rows = max_rows

    def verify(self, ctx: QueryContext, db_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Probe each SQL candidate and return execution state and final decision.
        """
        candidates: List[str] = ctx.sql_generation_state.get("candidates", [])
        execution_records: List[Dict[str, Any]] = []
        final_decision: Dict[str, Any] = {}

        for sql in candidates:
            probe = self.db_service.exec_probe(db_id=db_id, sql=sql, row_limit=self.max_rows)
            execution_records.append(self._to_record(sql, probe))
            if probe.status == "ok" and not final_decision:
                final_decision = {"sql": sql, "status": "ok", "result_summary": probe.summary}

        if not final_decision:
            final_decision = {"sql": None, "status": "failed", "reason": "no successful candidate"}

        execution_state = {
            "probes": execution_records,
            "sample_rows": execution_records[0].get("sample_rows") if execution_records else None,
        }
        return execution_state, final_decision

    def _to_record(self, sql: str, probe: ProbeResult) -> Dict[str, Any]:
        """
        Convert a ProbeResult into a serializable dict.
        """
        return {
            "sql": sql,
            "status": probe.status,
            "error_type": probe.error_type,
            "error_message": probe.error_message_short,
            "row_count": probe.row_count,
            "sample_rows": probe.sample_rows,
        }
