"""
Smoke test for the NL2SQL pipeline with stub components.
"""

from src.main import build_orchestrator
from src.api.models import QueryRequest


def test_pipeline_smoke():
    """
    Ensure the orchestrator runs end-to-end with stub services.
    """
    orchestrator = build_orchestrator()
    request = QueryRequest(user_id="tester", session_id="sess-test", query_text="上个月美国客户的订单金额总和是多少？")
    ctx = orchestrator.run(request)
    assert ctx["query_id"]
    assert ctx["router"]["chosen_db"]
    assert "linked_schema" in ctx["schema_state"]
    assert ctx["sql_generation_state"]["candidates"]
