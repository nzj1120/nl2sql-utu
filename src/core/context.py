"""
Definition of QueryContext, the shared state flowing through agents.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List
import uuid
import time

from src.api.models import QueryRequest


def now_ts() -> float:
    """
    Return a monotonic timestamp in seconds for latency tracking.
    """
    return time.time()


@dataclass
class QueryContext:
    """
    End-to-end context that every agent reads/writes incrementally.
    """

    query_id: str
    user: Dict[str, Any]
    session: Dict[str, Any]
    user_query: str
    router: Dict[str, Any] = field(default_factory=dict)
    schema_state: Dict[str, Any] = field(default_factory=dict)
    retrieval_state: Dict[str, Any] = field(default_factory=dict)
    sql_generation_state: Dict[str, Any] = field(default_factory=dict)
    execution_state: Dict[str, Any] = field(default_factory=dict)
    final_decision: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=lambda: {"token_usage": {}, "latency_ms": {}, "timestamps": {}})

    @classmethod
    def from_request(cls, request: QueryRequest) -> "QueryContext":
        """
        Build an empty context from the incoming query request.
        """
        ctx = cls(
            query_id=str(uuid.uuid4()),
            user={"id": request.user_id, "roles": [], "permissions": ["readonly" if request.options.readonly else "readwrite"]},
            session={"id": request.session_id, "history_summary": {}},
            user_query=request.query_text,
        )
        ctx.metrics["timestamps"]["start"] = now_ts()
        return ctx

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to a plain dict for persistence or response building.
        """
        return asdict(self)

    def close(self) -> None:
        """
        Mark context completion and record end timestamp.
        """
        self.metrics["timestamps"]["end"] = now_ts()
