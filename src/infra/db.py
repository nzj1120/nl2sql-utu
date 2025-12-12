"""
DB introspection service abstraction and a stub implementation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProbeResult:
    """
    Normalized result of a probe execution.
    """

    status: str
    row_count: int = 0
    sample_rows: Optional[List[Dict[str, Any]]] = field(default_factory=list)
    error_type: Optional[str] = None
    error_message_short: Optional[str] = None
    summary: Dict[str, Any] = field(default_factory=dict)


class DBIntrospectionService:
    """
    Interface for safe, read-only execution of probe SQL.
    """

    def exec_probe(self, db_id: str, sql: str, row_limit: int = 5) -> ProbeResult:
        """
        Execute a probing SQL statement and return a normalized result.
        """
        raise NotImplementedError("exec_probe must be implemented by subclasses")


class StubDBIntrospectionService(DBIntrospectionService):
    """
    Safe stub that simulates execution for testing flows without a database.
    """

    def exec_probe(self, db_id: str, sql: str, row_limit: int = 5) -> ProbeResult:
        """
        Simulate a probe: returns ok for SELECT with mock rows, otherwise an error.
        """
        sql_lower = sql.lower()
        if "select" in sql_lower:
            rows = [{"order_id": 1, "total_amount": 100.0}, {"order_id": 2, "total_amount": 200.0}]
            return ProbeResult(
                status="ok",
                row_count=len(rows),
                sample_rows=rows[:row_limit],
                summary={"message": "stubbed select", "row_count": len(rows)},
            )
        return ProbeResult(status="error", error_type="syntax", error_message_short="non-select probe rejected")
