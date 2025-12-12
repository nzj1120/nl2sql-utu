"""
Schema vector store abstraction plus a stubbed in-memory implementation.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


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


class SpiderSnowSchemaStore(SchemaVectorStoreService):
    """
    Schema store that reads Spider2-snow DB_schema JSON/DDL files directly.
    """

    def __init__(self, base_path: str):
        """
        Args:
            base_path: Root folder containing per-db directories with DB_schema (e.g., Spider2/spider2-snow/resource/databases).
        """
        self.base_path = base_path
        self._column_cache: Dict[str, List[ColumnSnippet]] = {}
        self._table_cache: Dict[str, List[str]] = {}

    def list_databases(self) -> List[str]:
        """
        List database ids available in the base path.
        """
        if not os.path.isdir(self.base_path):
            return []
        return sorted([d for d in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, d))])

    def list_tables(self, db_id: str) -> List[str]:
        """
        Return table names for a database.
        """
        self._ensure_loaded(db_id)
        return self._table_cache.get(db_id, [])

    def search_columns(self, db_id: str, query: str, exclude_cols: List[str], top_k: int) -> List[ColumnSnippet]:
        """
        Retrieve column snippets by simple keyword overlap on table/column names.
        """
        self._ensure_loaded(db_id)
        candidates = self._column_cache.get(db_id, [])
        if not candidates:
            return []

        exclude = set(exclude_cols)
        tokens = [tok for tok in re.split(r"[^a-zA-Z0-9_]+", query.lower()) if tok]

        def score(col: ColumnSnippet) -> Tuple[int, int]:
            name = col.name.lower()
            table = col.table.lower()
            hits = sum(tok in name or tok in table for tok in tokens)
            return hits, len(name)

        filtered = [c for c in candidates if c.id not in exclude]
        ranked = sorted(filtered, key=score, reverse=True)
        return ranked[:top_k]

    def _ensure_loaded(self, db_id: str) -> None:
        """
        Lazy-load schema columns and tables for a database.
        """
        if db_id in self._column_cache:
            return
        db_dir = os.path.join(self.base_path, db_id, db_id)
        if not os.path.isdir(db_dir):
            self._column_cache[db_id] = []
            self._table_cache[db_id] = []
            return

        columns: List[ColumnSnippet] = []
        tables: List[str] = []
        for entry in os.listdir(db_dir):
            if not entry.lower().endswith(".json"):
                continue
            json_path = os.path.join(db_dir, entry)
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    table_meta = json.load(f)
            except Exception:
                continue
            table_name = table_meta.get("table_name") or table_meta.get("table_fullname") or entry.replace(".json", "")
            short_table = table_name.split(".")[-1]
            tables.append(short_table)
            col_names = table_meta.get("column_names", [])
            col_types = table_meta.get("column_types", [])
            descriptions = table_meta.get("description", []) if isinstance(table_meta.get("description"), list) else []
            sample_rows = table_meta.get("sample_rows", [])
            for idx, col_name in enumerate(col_names):
                col_type = col_types[idx] if idx < len(col_types) else ""
                desc = descriptions[idx] if idx < len(descriptions) else None
                sample_vals = []
                if sample_rows and isinstance(sample_rows, list):
                    for row in sample_rows[:2]:
                        if isinstance(row, dict) and col_name in row:
                            sample_vals.append(str(row[col_name]))
                columns.append(
                    ColumnSnippet(
                        table=short_table,
                        name=col_name,
                        type=col_type,
                        description=desc or "",
                        sample_values=sample_vals,
                    )
                )
        self._column_cache[db_id] = columns
        self._table_cache[db_id] = sorted(set(tables))

    def db_catalog(self) -> List[Dict[str, str]]:
        """
        Return a lightweight catalog for RouterAgent consumption.
        """
        return [
            {"db_id": db_id, "name": db_id, "short_desc": "spider2-snow database", "example_tables": self.list_tables(db_id)}
            for db_id in self.list_databases()
        ]
