import pytest
from databricks.sdk.service.catalog import (
    CatalogInfo,
    ColumnInfo,
    ColumnTypeName,
    DataSourceFormat,
    SchemaInfo,
    TableInfo,
    TableType,
)

from openlakehouse.adapters.databricks_adapter import DatabricksAdapter
from openlakehouse.core.errors import QueryExecutionError, TableNotFoundError
from openlakehouse.core.models import ColumnType
from openlakehouse.core.sql_guard import UnsafeQueryError


def _make_adapter(mocker):
    mock_workspace_client = mocker.patch("openlakehouse.adapters.databricks_adapter.WorkspaceClient")
    adapter = DatabricksAdapter(
        name="db1", host="https://example.cloud.databricks.com", token="tok", warehouse_http_path="/sql/1.0/x"
    )
    return adapter, mock_workspace_client.return_value


def test_list_catalogs(mocker):
    adapter, ws = _make_adapter(mocker)
    ws.catalogs.list.return_value = [CatalogInfo(name="sales")]

    result = adapter.list_catalogs()

    assert len(result) == 1
    assert result[0].adapter == "db1"
    assert result[0].catalog == "sales"


def test_list_schemas(mocker):
    adapter, ws = _make_adapter(mocker)
    ws.schemas.list.return_value = [SchemaInfo(name="public")]

    result = adapter.list_schemas("sales")

    ws.schemas.list.assert_called_once_with(catalog_name="sales")
    assert result[0].schema_name == "public"


def test_list_tables_distinguishes_views_and_tables(mocker):
    adapter, ws = _make_adapter(mocker)
    ws.tables.list.return_value = [
        TableInfo(name="orders", table_type=TableType.MANAGED, comment="raw orders"),
        TableInfo(name="orders_view", table_type=TableType.VIEW),
    ]

    result = adapter.list_tables("sales", "public")
    by_name = {t.table_ref.table: t for t in result}

    assert by_name["orders"].table_type == "TABLE"
    assert by_name["orders"].comment == "raw orders"
    assert by_name["orders_view"].table_type == "VIEW"


def test_describe_table_maps_columns_and_partitions(mocker):
    adapter, ws = _make_adapter(mocker)
    ws.tables.get.return_value = TableInfo(
        name="orders",
        comment="raw orders",
        data_source_format=DataSourceFormat.DELTA,
        properties={"owner": "data-eng"},
        columns=[
            ColumnInfo(name="id", type_name=ColumnTypeName.LONG, type_text="bigint", nullable=False, position=0),
            ColumnInfo(
                name="dt",
                type_name=ColumnTypeName.DATE,
                type_text="date",
                nullable=True,
                position=1,
                partition_index=0,
            ),
        ],
    )

    schema = adapter.describe_table("sales", "public", "orders")

    ws.tables.get.assert_called_once_with(full_name="sales.public.orders")
    assert [c.name for c in schema.columns] == ["id", "dt"]
    assert schema.columns[0].type == ColumnType.BIGINT
    assert schema.columns[0].nullable is False
    assert schema.columns[1].is_partition_key is True
    assert schema.partition_columns == ["dt"]
    assert schema.table_format == "DELTA"
    assert schema.properties == {"owner": "data-eng"}


def test_describe_table_not_found_raises(mocker):
    adapter, ws = _make_adapter(mocker)
    ws.tables.get.side_effect = Exception("not found")

    with pytest.raises(TableNotFoundError):
        adapter.describe_table("sales", "public", "missing")


def test_execute_query_rejects_write_statement(mocker):
    adapter, _ = _make_adapter(mocker)
    with pytest.raises(UnsafeQueryError):
        adapter.execute_query("DELETE FROM sales.public.orders")


def test_execute_query_returns_rows_and_truncation_flag(mocker):
    adapter, _ = _make_adapter(mocker)

    mock_cursor = mocker.MagicMock()
    mock_cursor.description = [("id", "bigint"), ("amount", "double")]
    mock_cursor.fetchmany.return_value = [(1, 10.0), (2, 20.0)]
    mock_cursor.fetchone.return_value = (3, 30.0)  # signals more rows exist
    mock_cursor.__enter__.return_value = mock_cursor

    mock_conn = mocker.MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__.return_value = mock_conn

    mock_connect = mocker.patch(
        "openlakehouse.adapters.databricks_adapter.databricks_sql.connect", return_value=mock_conn
    )

    result = adapter.execute_query("SELECT * FROM sales.public.orders", catalog="sales", schema="public", max_rows=2)

    mock_connect.assert_called_once_with(
        server_hostname="example.cloud.databricks.com",
        http_path="/sql/1.0/x",
        access_token="tok",
        catalog="sales",
        schema="public",
    )
    assert result.rows == [[1, 10.0], [2, 20.0]]
    assert result.row_count == 2
    assert result.truncated is True


def test_execute_query_wraps_driver_errors(mocker):
    adapter, _ = _make_adapter(mocker)
    mocker.patch(
        "openlakehouse.adapters.databricks_adapter.databricks_sql.connect",
        side_effect=RuntimeError("connection refused"),
    )

    with pytest.raises(QueryExecutionError, match="connection refused"):
        adapter.execute_query("SELECT 1")
