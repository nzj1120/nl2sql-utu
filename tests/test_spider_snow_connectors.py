"""
Connector test against local Spider2-snow DB_schema data if available.
"""

import os
from pathlib import Path

import pytest

from src.infra.vector_store import SpiderSnowSchemaStore
from src.infra.db import SpiderSnowDBIntrospectionService


SPIDER_BASE = Path(__file__).resolve().parents[2] / "Spider2" / "spider2-snow" / "resource" / "databases"


@pytest.mark.skipif(not SPIDER_BASE.is_dir(), reason="Spider2-snow data not available")
def test_spider_schema_store_loads():
    """
    Ensure schema store loads tables and columns from Spider2-snow resources.
    """
    store = SpiderSnowSchemaStore(str(SPIDER_BASE))
    dbs = store.list_databases()
    assert dbs, "should list databases"
    db_id = dbs[0]
    tables = store.list_tables(db_id)
    assert tables, "should list tables"
    cols = store.search_columns(db_id=db_id, query=tables[0], exclude_cols=[], top_k=3)
    assert cols, "should retrieve columns"


@pytest.mark.skipif(not SPIDER_BASE.is_dir(), reason="Spider2-snow data not available")
def test_spider_db_probe_reads_samples():
    """
    Ensure DB introspection returns sample rows for a table.
    """
    store = SpiderSnowSchemaStore(str(SPIDER_BASE))
    db_id = store.list_databases()[0]
    tables = store.list_tables(db_id)
    table = tables[0]
    db_service = SpiderSnowDBIntrospectionService(str(SPIDER_BASE))
    probe = db_service.exec_probe(db_id=db_id, sql=f"select * from {table} limit 3")
    assert probe.status == "ok"
    assert isinstance(probe.sample_rows, list)
