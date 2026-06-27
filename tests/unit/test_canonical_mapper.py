"""Unit tests for canonical mapper functions (internal → canonical models)."""
from openlakehouse.core.canonical.mapper import (
    catalog_to_canonical,
    column_to_canonical,
    query_result_to_canonical,
    schema_to_canonical,
    table_schema_to_canonical,
    table_summary_to_canonical,
)
from openlakehouse.core.canonical.metadata import CanonicalDataType, CanonicalTableType
from openlakehouse.core.models import (
    CatalogRef,
    ColumnSchema,
    ColumnType,
    QueryResult,
    SchemaRef,
    TableRef,
    TableSchema,
    TableSummary,
)


def test_catalog_to_canonical_databricks():
    ref = CatalogRef(adapter="databricks_prod", catalog="sales")
    result = catalog_to_canonical(ref, "databricks")
    assert result.adapter == "databricks_prod"
    assert result.platform == "databricks"
    assert result.catalog == "sales"
    assert result.native_catalog == "sales"


def test_catalog_to_canonical_aws():
    ref = CatalogRef(adapter="aws_prod", catalog="AwsDataCatalog")
    result = catalog_to_canonical(ref, "aws")
    assert result.platform == "aws"
    assert result.catalog == "AwsDataCatalog"
    assert result.native_catalog == "AwsDataCatalog"


def test_schema_to_canonical():
    ref = SchemaRef(adapter="databricks_prod", catalog="sales", schema="orders")
    result = schema_to_canonical(ref, "databricks")
    assert result.schema == "orders"
    assert result.native_schema == "orders"
    assert result.platform == "databricks"
    assert result.catalog == "sales"


def test_table_summary_to_canonical_table():
    t = TableSummary(
        table_ref=TableRef(adapter="db", catalog="c", schema="s", table="orders"),
        table_type="TABLE",
        comment="main orders table",
    )
    result = table_summary_to_canonical(t, "databricks")
    assert result.table_type == CanonicalTableType.TABLE
    assert result.table == "orders"
    assert result.comment == "main orders table"
    assert result.platform == "databricks"


def test_table_summary_to_canonical_view():
    t = TableSummary(
        table_ref=TableRef(adapter="db", catalog="c", schema="s", table="v"),
        table_type="VIEW",
    )
    result = table_summary_to_canonical(t, "aws")
    assert result.table_type == CanonicalTableType.VIEW


def test_column_to_canonical_type_mapping():
    cases = [
        (ColumnType.STRING, CanonicalDataType.STRING),
        (ColumnType.INTEGER, CanonicalDataType.INTEGER),
        (ColumnType.BIGINT, CanonicalDataType.BIGINT),
        (ColumnType.DOUBLE, CanonicalDataType.DOUBLE),
        (ColumnType.TIMESTAMP, CanonicalDataType.TIMESTAMP),
        (ColumnType.BOOLEAN, CanonicalDataType.BOOLEAN),
        (ColumnType.UNKNOWN, CanonicalDataType.UNKNOWN),
    ]
    for col_type, expected in cases:
        col = ColumnSchema(name="x", type=col_type, raw_type=col_type.value)
        result = column_to_canonical(col)
        assert result.data_type == expected, f"Failed for {col_type}"


def test_column_to_canonical_preserves_metadata():
    col = ColumnSchema(
        name="pickup_date",
        type=ColumnType.DATE,
        raw_type="date",
        nullable=False,
        comment="trip pickup date",
        is_partition_key=True,
        ordinal_position=0,
    )
    result = column_to_canonical(col)
    assert result.name == "pickup_date"
    assert result.nullable is False
    assert result.comment == "trip pickup date"
    assert result.is_partition_key is True
    assert result.ordinal_position == 0


def test_table_schema_to_canonical():
    ts = TableSchema(
        table_ref=TableRef(adapter="aws_prod", catalog="AwsDataCatalog", schema="analytics", table="trips"),
        columns=[ColumnSchema(name="distance", type=ColumnType.DOUBLE, raw_type="double")],
        partition_columns=["pickup_date"],
        table_format="PARQUET",
        comment="NYC taxi trips",
        properties={"created_by": "glue"},
    )
    result = table_schema_to_canonical(ts, "aws")
    assert result.table.platform == "aws"
    assert result.table.catalog == "AwsDataCatalog"
    assert result.table.schema == "analytics"
    assert len(result.columns) == 1
    assert result.columns[0].data_type == CanonicalDataType.DOUBLE
    assert result.partition_columns == ["pickup_date"]
    assert result.table_format == "PARQUET"
    assert result.properties == {"created_by": "glue"}


def test_query_result_to_canonical():
    qr = QueryResult(
        columns=[
            ColumnSchema(name="n", type=ColumnType.INTEGER, raw_type="integer"),
            ColumnSchema(name="label", type=ColumnType.STRING, raw_type="varchar"),
        ],
        rows=[[1, "a"], [2, "b"]],
        row_count=2,
        truncated=False,
        next_page_token=None,
        query_id="abc-123",
    )
    result = query_result_to_canonical(qr, "aws_prod", "aws", execution_time_ms=420.0)
    assert len(result.columns) == 2
    assert result.columns[0].data_type == CanonicalDataType.INTEGER
    assert result.columns[1].data_type == CanonicalDataType.STRING
    assert result.rows == [[1, "a"], [2, "b"]]
    assert result.pagination.row_count == 2
    assert result.pagination.truncated is False
    assert result.pagination.next_page_token is None
    assert result.execution.query_id == "abc-123"
    assert result.execution.adapter == "aws_prod"
    assert result.execution.platform == "aws"
    assert result.execution.execution_time_ms == 420.0


def test_query_result_to_canonical_with_pagination():
    qr = QueryResult(
        columns=[ColumnSchema(name="id", type=ColumnType.BIGINT, raw_type="bigint")],
        rows=[[i] for i in range(1000)],
        row_count=1000,
        truncated=True,
        next_page_token="exec-id:next-token-value",
        query_id="exec-id",
    )
    result = query_result_to_canonical(qr, "aws_prod", "aws")
    assert result.pagination.truncated is True
    assert result.pagination.next_page_token == "exec-id:next-token-value"
    assert result.pagination.row_count == 1000
