"""
Request and response models for the NL2SQL API layer.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid
import time


@dataclass
class QueryOptions:
    """
    Options attached to a request to control generation/runtime behavior.
    """

    temperature: float = 0.3
    readonly: bool = True
    max_latency_ms: int = 5000


@dataclass
class QueryRequest:
    """
    Incoming query payload built by API/UI/queue consumers.
    """

    user_id: str
    session_id: str
    query_text: str
    options: QueryOptions = field(default_factory=QueryOptions)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the request to a plain dict for logging or persistence.
        """
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "query_text": self.query_text,
            "options": self.options.__dict__,
        }


@dataclass
class QueryResponse:
    """
    Lightweight response returned to the caller while the full QueryContext is persisted.
    """

    query_id: str
    session_id: str
    status: str
    message: str
    sql: Optional[str] = None
    result_preview: Optional[List[Dict[str, Any]]] = None
    latency_ms: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(cls, ctx: Dict[str, Any], status: str, message: str) -> "QueryResponse":
        """
        Build a QueryResponse from a QueryContext dict representation.
        """
        return cls(
            query_id=ctx.get("query_id", str(uuid.uuid4())),
            session_id=ctx.get("session", {}).get("id", ""),
            status=status,
            message=message,
            sql=ctx.get("final_decision", {}).get("sql"),
            result_preview=ctx.get("execution_state", {}).get("sample_rows"),
            latency_ms=_calc_latency(ctx),
            meta={"metrics": ctx.get("metrics", {})},
        )


def _calc_latency(ctx: Dict[str, Any]) -> Optional[int]:
    """
    Compute latency from stored timestamps if available.
    """
    start_ts = ctx.get("metrics", {}).get("timestamps", {}).get("start")
    end_ts = ctx.get("metrics", {}).get("timestamps", {}).get("end")
    if start_ts is None or end_ts is None:
        return None
    return int((end_ts - start_ts) * 1000)
