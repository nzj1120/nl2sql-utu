"""
Orchestrator that wires API requests through all agents.
"""

from typing import Any, Dict, List, Optional

from src.api.models import QueryRequest
from src.core.context import QueryContext
from src.agents.router import RouterAgent
from src.agents.schema import SchemaAgent
from src.agents.sql_generator import SQLGeneratorAgent
from src.agents.verifier import VerifierAgent
from src.infra.storage import ContextStore
from src.infra.vector_store import SchemaVectorStoreService


class Orchestrator:
    """
    Coordinates Router → Schema → SQL Generator → Verifier.
    """

    def __init__(
        self,
        router: RouterAgent,
        schema_agent: SchemaAgent,
        sql_generator: SQLGeneratorAgent,
        verifier: VerifierAgent,
        vector_store: SchemaVectorStoreService,
        context_store: Optional[ContextStore] = None,
        db_catalog: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Create an orchestrator with all agent dependencies.
        """
        self.router = router
        self.schema_agent = schema_agent
        self.sql_generator = sql_generator
        self.verifier = verifier
        self.vector_store = vector_store
        self.context_store = context_store
        self.db_catalog = db_catalog or []

    def run(self, request: QueryRequest) -> Dict[str, Any]:
        """
        Execute the full NL2SQL pipeline and return the final QueryContext as dict.
        """
        ctx = QueryContext.from_request(request)
        table_catalog = {db["db_id"]: db for db in self.db_catalog}

        router_output = self.router.route(ctx.user_query, table_catalog)
        ctx.router = router_output

        chosen_db = router_output.get("chosen_db")
        table_list = self._get_table_list(chosen_db)

        ctx = self.schema_agent.run(
            user_query=ctx.user_query,
            db_id=chosen_db,
            table_list=table_list,
            ctx=ctx,
        )

        sql_state = self.sql_generator.generate(ctx)
        ctx.sql_generation_state = sql_state

        verify_state, final_decision = self.verifier.verify(ctx, chosen_db)
        ctx.execution_state = verify_state
        ctx.final_decision = final_decision

        ctx.close()
        self._persist(ctx)
        return ctx.to_dict()

    def _get_table_list(self, db_id: Optional[str]) -> List[str]:
        """
        Fetch a table list for the selected database from catalog or vector store stub.
        """
        if db_id is None:
            return []
        if self.vector_store:
            tables = self.vector_store.list_tables(db_id)
            if tables:
                return tables
        for db in self.db_catalog:
            if db.get("db_id") == db_id:
                return db.get("example_tables", [])
        return []

    def _persist(self, ctx: QueryContext) -> None:
        """
        Persist the context if a store is configured.
        """
        if self.context_store:
            self.context_store.save(ctx)

    def agent_summary(self) -> Dict[str, str]:
        """
        Return short descriptions of the wired agents for observability endpoints.
        """
        return {
            "router": self.router.name,
            "schema_agent": self.schema_agent.name,
            "sql_generator": self.sql_generator.name,
            "verifier": self.verifier.name,
        }
