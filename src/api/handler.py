"""
Entry functions that connect API/UI requests to the orchestrator.
"""

from typing import Dict, Any

from src.api.models import QueryRequest, QueryResponse
from src.core.pipeline import Orchestrator


class RequestHandler:
    """
    Simple facade to hide orchestrator wiring from the API layer.
    """

    def __init__(self, orchestrator: Orchestrator):
        """
        Create a handler with a preconfigured orchestrator instance.
        """
        self.orchestrator = orchestrator

    def handle(self, request: QueryRequest) -> QueryResponse:
        """
        Execute the NL2SQL pipeline for a single request.
        """
        ctx = self.orchestrator.run(request)
        return QueryResponse.from_context(ctx, status="ok", message="completed")

    def health(self) -> Dict[str, Any]:
        """
        Provide a minimal health/info payload for monitoring endpoints.
        """
        return {"status": "ok", "agents": self.orchestrator.agent_summary()}
