"""
Schema vector store abstraction plus a stubbed in-memory implementation.
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class ColumnSnippet:
    """
    Compact column record returned by vector search.
    """

    table: str
    name: str
    type: str = "TEXT"
    description: str = ""
    is_pk: bool = False
    is_fk: bool = False
    sample_values: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """
        Unique identifier for deduplication.
        """
        return f"{self.table}.{self.name}"


class SchemaVectorStoreService:
    """
    Interface for column-level retrieval using embeddings.
    """

    def search_columns(self, db_id: str, query: str, exclude_cols: List[str], top_k: int) -> List[ColumnSnippet]:
        """
        Retrieve column snippets relevant to the query. Override in production.
        """
        raise NotImplementedError("search_columns must be implemented by subclasses")

    def list_tables(self, db_id: str) -> List[str]:
        """
        List available tables for a database. Override in production.
        """
        return []


class StubSchemaVectorStore(SchemaVectorStoreService):
    """
    Minimal stub that returns deterministic columns for testing.
    """

    def __init__(self):
        self.mock_schema: Dict[str, List[ColumnSnippet]] = {
            "sales": [
                ColumnSnippet(table="orders", name="order_id", type="INT", is_pk=True),
                ColumnSnippet(table="orders", name="customer_id", type="INT", is_fk=True),
                ColumnSnippet(table="orders", name="order_date", type="DATE"),
                ColumnSnippet(table="orders", name="total_amount", type="NUMERIC"),
                ColumnSnippet(table="customers", name="customer_id", type="INT", is_pk=True),
                ColumnSnippet(table="customers", name="country", type="TEXT"),
            ]
        }

    def search_columns(self, db_id: str, query: str, exclude_cols: List[str], top_k: int) -> List[ColumnSnippet]:
        """
        Return a slice of the mock schema, excluding already seen columns.
        """
        cols = [c for c in self.mock_schema.get(db_id, []) if c.id not in set(exclude_cols)]
        return cols[:top_k]

    def list_tables(self, db_id: str) -> List[str]:
        """
        Return table names from the stub schema.
        """
        cols = self.mock_schema.get(db_id, [])
        return sorted({c.table for c in cols})
