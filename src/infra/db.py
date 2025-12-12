"""
DB introspection service abstraction and a stub implementation.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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


class SpiderSnowDBIntrospectionService(DBIntrospectionService):
    """
    Probe service backed by Spider2-snow DB_schema JSON sample rows.
    """

    def __init__(self, base_path: str):
        """
        Args:
            base_path: Root folder containing per-db schema directories (Spider2/spider2-snow/resource/databases).
        """
        self.base_path = base_path
        self._table_meta: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def exec_probe(self, db_id: str, sql: str, row_limit: int = 5) -> ProbeResult:
        """
        Execute a lightweight probe: supports simple SELECT ... FROM <table> queries by returning sample_rows.
        For unsupported patterns, returns an error observation.
        """
        table_key = self._extract_table(db_id, sql)
        if not table_key:
            return ProbeResult(status="error", error_type="unsupported", error_message_short="unsupported SQL pattern")

        table_meta = self._load_table_meta(db_id, table_key)
        if not table_meta:
            return ProbeResult(status="error", error_type="missing_table", error_message_short=f"table {table_key} not found")

        sample_rows = table_meta.get("sample_rows", []) or []
        limited_rows = sample_rows[:row_limit] if isinstance(sample_rows, list) else []
        return ProbeResult(
            status="ok",
            row_count=len(limited_rows),
            sample_rows=limited_rows,
            summary={"message": "sample_rows", "table": table_meta.get("table_fullname", table_key)},
        )

    def _extract_table(self, db_id: str, sql: str) -> Optional[str]:
        """
        Parse a table name from a simple SELECT ... FROM clause.
        """
        match = re.search(r"from\s+([^\s;]+)", sql, flags=re.IGNORECASE)
        if not match:
            return None
        raw = match.group(1).strip().strip(";")
        raw = raw.strip('"').strip("'")
        # take last component to align with JSON filenames
        return raw.split(".")[-1]

    def _load_table_meta(self, db_id: str, table: str) -> Optional[Dict[str, Any]]:
        """
        Load table metadata JSON and cache it.
        """
        key = (db_id, table.lower())
        if key in self._table_meta:
            return self._table_meta[key]

        db_dir = os.path.join(self.base_path, db_id, db_id)
        if not os.path.isdir(db_dir):
            return None
        candidate = os.path.join(db_dir, f"{table}.json")
        if not os.path.exists(candidate):
            # try upper/lower variations
            alt = os.path.join(db_dir, f"{table.upper()}.json")
            alt2 = os.path.join(db_dir, f"{table.lower()}.json")
            candidate = alt if os.path.exists(alt) else alt2
        if not os.path.exists(candidate):
            return None
        try:
            with open(candidate, "r", encoding="utf-8") as f:
                meta = json.load(f)
                self._table_meta[key] = meta
                return meta
        except Exception:
            return None


class SnowflakeProbeService(DBIntrospectionService):
    """
    Online probe service backed by a Snowflake warehouse (read-only usage).
    """

    def __init__(self, credential_path: str, default_db: Optional[str] = None, default_schema: Optional[str] = None, warehouse: Optional[str] = None, role: Optional[str] = None):
        """
        Args:
            credential_path: Path to JSON credential file (compatible with spider-agent-snow snowflake_credential.json).
            default_db: Default database to USE.
            default_schema: Default schema to USE.
            warehouse: Warehouse name override.
            role: Role override.
        """
        self.credential_path = credential_path
        self.default_db = default_db
        self.default_schema = default_schema
        self.warehouse = warehouse
        self.role = role
        self._cred_cache: Optional[Dict[str, Any]] = None

    def exec_probe(self, db_id: str, sql: str, row_limit: int = 5) -> ProbeResult:
        """
        Execute a SELECT probe against Snowflake, enforcing read-only and row limits.
        """
        if not self._cred_cache:
            self._cred_cache = self._load_credentials()
        if not self._cred_cache:
            return ProbeResult(status="error", error_type="credential", error_message_short="missing snowflake credentials")

        if not self._is_select(sql):
            return ProbeResult(status="error", error_type="forbidden", error_message_short="only SELECT probes allowed")

        safe_sql = self._enforce_limit(sql, row_limit)

        try:
            import snowflake.connector  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            return ProbeResult(status="error", error_type="missing_dep", error_message_short=f"install snowflake-connector-python: {exc}")

        try:
            conn = snowflake.connector.connect(
                account=self._cred_cache.get("account"),
                user=self._cred_cache.get("user"),
                password=self._cred_cache.get("password"),
                warehouse=self.warehouse or self._cred_cache.get("warehouse"),
                database=self.default_db or db_id or self._cred_cache.get("database"),
                schema=self.default_schema or self._cred_cache.get("schema"),
                role=self.role or self._cred_cache.get("role"),
            )
            cur = conn.cursor()
            if db_id:
                cur.execute(f'USE DATABASE "{db_id}"')
            if self.default_schema:
                cur.execute(f'USE SCHEMA "{self.default_schema}"')
            cur.execute(safe_sql)
            rows = cur.fetchmany(row_limit)
            col_names = [c[0] for c in cur.description] if cur.description else []
            sample_rows = [dict(zip(col_names, r)) for r in rows]
            cur.close()
            conn.close()
            return ProbeResult(
                status="ok",
                row_count=len(sample_rows),
                sample_rows=sample_rows,
                summary={"message": "snowflake probe", "table_hint": self._extract_table(db_id, sql)},
            )
        except Exception as exc:  # pragma: no cover - network/db errors
            return ProbeResult(status="error", error_type="db_error", error_message_short=str(exc))

    def _load_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Load credentials from JSON file.
        """
        if not os.path.exists(self.credential_path):
            return None
        try:
            with open(self.credential_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _is_select(self, sql: str) -> bool:
        """
        Allow only SELECT-like statements.
        """
        forbidden = re.compile(r"\b(insert|update|delete|merge|alter|drop|truncate|create)\b", re.IGNORECASE)
        return bool(re.match(r"\s*select\b", sql, flags=re.IGNORECASE)) and not forbidden.search(sql)

    def _enforce_limit(self, sql: str, row_limit: int) -> str:
        """
        Ensure a LIMIT clause is present to bound results.
        """
        if re.search(r"\blimit\s+\d+", sql, flags=re.IGNORECASE):
            return sql
        return f"{sql.rstrip().rstrip(';')} LIMIT {row_limit}"
