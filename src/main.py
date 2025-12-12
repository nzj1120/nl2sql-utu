"""
Minimal CLI entry to run the NL2SQL pipeline with stubbed services.
"""

import argparse

from src.api.models import QueryRequest, QueryOptions
from src.api.handler import RequestHandler
from src.core.pipeline import Orchestrator
from src.agents.router import RouterAgent
from src.agents.schema import SchemaAgent, SchemaAgentConfig
from src.agents.sql_generator import SQLGeneratorAgent
from src.agents.verifier import VerifierAgent
from src.infra.llm import EchoLLMClient
from src.infra.vector_store import StubSchemaVectorStore
from src.infra.db import StubDBIntrospectionService
from src.infra.storage import ContextStore


def build_orchestrator() -> Orchestrator:
    """
    Wire stub services and agents into an orchestrator.
    """
    llm = EchoLLMClient()
    vector_store = StubSchemaVectorStore()
    db_service = StubDBIntrospectionService()
    router = RouterAgent(llm=llm)
    schema_agent = SchemaAgent(llm=llm, vector_store=vector_store, db_service=db_service, config=SchemaAgentConfig())
    sql_generator = SQLGeneratorAgent(llm=llm)
    verifier = VerifierAgent(db_service=db_service)
    context_store = ContextStore()

    db_catalog = [
        {"db_id": "sales", "name": "Sales DW", "short_desc": "订单与客户数据", "example_tables": ["orders", "customers"]},
    ]

    return Orchestrator(
        router=router,
        schema_agent=schema_agent,
        sql_generator=sql_generator,
        verifier=verifier,
        vector_store=vector_store,
        context_store=context_store,
        db_catalog=db_catalog,
    )


def main() -> None:
    """
    Parse arguments and run a single NL2SQL request through the pipeline.
    """
    parser = argparse.ArgumentParser(description="Run NL2SQL YouTu agent pipeline with stub components.")
    parser.add_argument("--query", required=True, help="Natural language question.")
    parser.add_argument("--user-id", default="u123", help="User identifier.")
    parser.add_argument("--session-id", default="sess-demo", help="Session identifier.")
    args = parser.parse_args()

    orchestrator = build_orchestrator()
    handler = RequestHandler(orchestrator)
    request = QueryRequest(user_id=args.user_id, session_id=args.session_id, query_text=args.query, options=QueryOptions())
    response = handler.handle(request)
    print("Response:", response)


if __name__ == "__main__":
    main()
