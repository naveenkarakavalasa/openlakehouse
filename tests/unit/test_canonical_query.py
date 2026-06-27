"""Unit tests for canonical query models."""
from openlakehouse.core.canonical.metadata import CanonicalDataType
from openlakehouse.core.canonical.query import (
    CanonicalExecutionMetadata,
    CanonicalPagination,
    CanonicalQueryColumn,
    CanonicalQueryRequest,
    CanonicalQueryResult,
)


def test_canonical_query_column():
    col = CanonicalQueryColumn(
        name="fare_amount",
        data_type=CanonicalDataType.DOUBLE,
        raw_type="double",
    )
    assert col.name == "fare_amount"
    assert col.data_type == CanonicalDataType.DOUBLE
    assert col.nullable is True


def test_canonical_pagination_defaults():
    page = CanonicalPagination(row_count=5)
    assert page.truncated is False
    assert page.next_page_token is None
    assert page.row_count == 5


def test_canonical_pagination_with_token():
    page = CanonicalPagination(
        truncated=True, next_page_token="abc123:def456", row_count=1000
    )
    assert page.truncated is True
    assert page.next_page_token == "abc123:def456"


def test_canonical_execution_metadata_databricks():
    meta = CanonicalExecutionMetadata(
        query_id=None,
        adapter="databricks_prod",
        platform="databricks",
        execution_time_ms=250.5,
    )
    assert meta.platform == "databricks"
    assert meta.query_id is None
    assert meta.execution_time_ms == 250.5
    assert meta.native_metadata == {}


def test_canonical_execution_metadata_aws():
    meta = CanonicalExecutionMetadata(
        query_id="9b83ecec-3206-49e2-9b7a-881a651df252",
        adapter="aws_prod",
        platform="aws",
        execution_time_ms=1800.0,
        native_metadata={"WorkGroup": "primary"},
    )
    assert meta.query_id == "9b83ecec-3206-49e2-9b7a-881a651df252"
    assert meta.native_metadata["WorkGroup"] == "primary"


def test_canonical_query_result_structure():
    result = CanonicalQueryResult(
        columns=[
            CanonicalQueryColumn(name="n", data_type=CanonicalDataType.INTEGER, raw_type="integer")
        ],
        rows=[["1"]],
        pagination=CanonicalPagination(row_count=1),
        execution=CanonicalExecutionMetadata(adapter="aws_prod", platform="aws"),
    )
    assert len(result.columns) == 1
    assert result.rows == [["1"]]
    assert result.pagination.row_count == 1
    assert result.execution.platform == "aws"


def test_canonical_query_result_serializes_cleanly():
    result = CanonicalQueryResult(
        columns=[
            CanonicalQueryColumn(name="id", data_type=CanonicalDataType.BIGINT, raw_type="bigint")
        ],
        rows=[[1], [2]],
        pagination=CanonicalPagination(row_count=2),
        execution=CanonicalExecutionMetadata(adapter="db", platform="databricks"),
    )
    data = result.model_dump()
    assert "columns" in data
    assert "rows" in data
    assert "pagination" in data
    assert "execution" in data
    assert data["columns"][0]["data_type"] == "bigint"


def test_canonical_query_request():
    req = CanonicalQueryRequest(
        adapter="databricks_prod",
        sql="SELECT 1 AS n",
        catalog="sales",
        schema="orders",
        max_rows=500,
    )
    assert req.adapter == "databricks_prod"
    assert req.page_token is None
