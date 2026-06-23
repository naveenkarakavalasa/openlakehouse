import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from openlakehouse.adapters.aws_adapter import AWSAdapter
from openlakehouse.core.errors import PermissionDeniedError, QueryExecutionError, TableNotFoundError
from openlakehouse.core.sql_guard import UnsafeQueryError

REGION = "us-east-1"
OUTPUT_LOCATION = "s3://my-bucket/athena-results/"


def _make_adapter(region=REGION):
    return AWSAdapter(
        name="aws1",
        region=region,
        athena_output_location=OUTPUT_LOCATION,
    )


@mock_aws
def test_list_catalogs_returns_single_glue_catalog():
    adapter = _make_adapter()
    catalogs = adapter.list_catalogs()
    assert len(catalogs) == 1
    assert catalogs[0].catalog == "AwsDataCatalog"
    assert catalogs[0].adapter == "aws1"


@mock_aws
def test_list_schemas_lists_glue_databases():
    boto3.client("glue", region_name=REGION).create_database(DatabaseInput={"Name": "analytics"})
    adapter = _make_adapter()

    schemas = adapter.list_schemas("AwsDataCatalog")

    assert [s.schema_name for s in schemas] == ["analytics"]
    assert schemas[0].adapter == "aws1"
    assert schemas[0].catalog == "AwsDataCatalog"


@mock_aws
def test_list_tables_distinguishes_views_and_tables():
    glue = boto3.client("glue", region_name=REGION)
    glue.create_database(DatabaseInput={"Name": "analytics"})
    glue.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "orders", "StorageDescriptor": {"Columns": []}},
    )
    glue.create_table(
        DatabaseName="analytics",
        TableInput={"Name": "orders_view", "TableType": "VIRTUAL_VIEW", "StorageDescriptor": {"Columns": []}},
    )
    adapter = _make_adapter()

    tables = adapter.list_tables("AwsDataCatalog", "analytics")
    by_name = {t.table_ref.table: t for t in tables}

    assert by_name["orders"].table_type == "TABLE"
    assert by_name["orders_view"].table_type == "VIEW"


@mock_aws
def test_describe_table_maps_columns_and_partitions():
    glue = boto3.client("glue", region_name=REGION)
    glue.create_database(DatabaseInput={"Name": "analytics"})
    glue.create_table(
        DatabaseName="analytics",
        TableInput={
            "Name": "orders",
            "StorageDescriptor": {
                "Columns": [{"Name": "id", "Type": "bigint"}, {"Name": "amount", "Type": "double"}],
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            },
            "PartitionKeys": [{"Name": "dt", "Type": "string"}],
            "Parameters": {"classification": "parquet"},
        },
    )
    adapter = _make_adapter()

    schema = adapter.describe_table("AwsDataCatalog", "analytics", "orders")

    names = [c.name for c in schema.columns]
    assert names == ["id", "amount", "dt"]
    assert schema.partition_columns == ["dt"]
    assert [c.is_partition_key for c in schema.columns] == [False, False, True]
    assert schema.table_format == "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"


@mock_aws
def test_describe_table_not_found_raises_table_not_found_error():
    boto3.client("glue", region_name=REGION).create_database(DatabaseInput={"Name": "analytics"})
    adapter = _make_adapter()

    with pytest.raises(TableNotFoundError):
        adapter.describe_table("AwsDataCatalog", "analytics", "does_not_exist")


def test_execute_query_rejects_write_statement():
    adapter = _make_adapter()
    with pytest.raises(UnsafeQueryError):
        adapter.execute_query("DROP TABLE analytics.orders")


def test_execute_query_strips_header_row_on_first_page(mocker):
    adapter = _make_adapter()

    mocker.patch.object(
        adapter._athena,
        "start_query_execution",
        return_value={"QueryExecutionId": "qid-1"},
    )
    mocker.patch.object(
        adapter._athena,
        "get_query_execution",
        return_value={"QueryExecution": {"Status": {"State": "SUCCEEDED"}}},
    )
    mocker.patch.object(
        adapter._athena,
        "get_query_results",
        return_value={
            "ResultSet": {
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id", "Type": "bigint"}]},
                "Rows": [
                    {"Data": [{"VarCharValue": "id"}]},  # header row, must be stripped
                    {"Data": [{"VarCharValue": "1"}]},
                    {"Data": [{"VarCharValue": "2"}]},
                ],
            }
        },
    )

    result = adapter.execute_query("SELECT * FROM analytics.orders")

    assert result.rows == [["1"], ["2"]]
    assert result.row_count == 2
    assert result.truncated is False
    assert result.query_id == "qid-1"


def test_execute_query_pagination_token_round_trips(mocker):
    adapter = _make_adapter()

    mocker.patch.object(
        adapter._athena, "start_query_execution", return_value={"QueryExecutionId": "qid-2"}
    )
    mocker.patch.object(
        adapter._athena,
        "get_query_execution",
        return_value={"QueryExecution": {"Status": {"State": "SUCCEEDED"}}},
    )
    mocker.patch.object(
        adapter._athena,
        "get_query_results",
        return_value={
            "ResultSet": {
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id", "Type": "bigint"}]},
                "Rows": [{"Data": [{"VarCharValue": "id"}]}, {"Data": [{"VarCharValue": "1"}]}],
            },
            "NextToken": "athena-next-token",
        },
    )

    first_page = adapter.execute_query("SELECT * FROM analytics.orders", max_rows=1)

    assert first_page.truncated is True
    assert first_page.next_page_token == "qid-2:athena-next-token"

    # Resuming with the page token should call get_query_results with NextToken
    # and the underlying query execution id, not start a new query.
    get_results_mock = mocker.patch.object(
        adapter._athena,
        "get_query_results",
        return_value={
            "ResultSet": {
                "ResultSetMetadata": {"ColumnInfo": [{"Name": "id", "Type": "bigint"}]},
                "Rows": [{"Data": [{"VarCharValue": "2"}]}],
            }
        },
    )
    start_mock = mocker.patch.object(adapter._athena, "start_query_execution")

    second_page = adapter.execute_query(
        "SELECT * FROM analytics.orders", max_rows=1, page_token=first_page.next_page_token
    )

    start_mock.assert_not_called()
    get_results_mock.assert_called_once_with(
        QueryExecutionId="qid-2", MaxResults=1, NextToken="athena-next-token"
    )
    assert second_page.rows == [["2"]]
    assert second_page.truncated is False


def test_execute_query_failed_state_raises_query_execution_error(mocker):
    adapter = _make_adapter()
    mocker.patch.object(
        adapter._athena, "start_query_execution", return_value={"QueryExecutionId": "qid-3"}
    )
    mocker.patch.object(
        adapter._athena,
        "get_query_execution",
        return_value={
            "QueryExecution": {"Status": {"State": "FAILED", "StateChangeReason": "syntax error"}}
        },
    )

    with pytest.raises(QueryExecutionError, match="syntax error"):
        adapter.execute_query("SELECT * FROM analytics.orders")


def test_access_denied_client_error_maps_to_permission_denied(mocker):
    adapter = _make_adapter()
    error = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException", "Message": "nope"}},
        operation_name="GetTables",
    )
    mocker.patch.object(adapter._glue, "get_paginator", side_effect=error)

    with pytest.raises(PermissionDeniedError):
        adapter.list_tables("AwsDataCatalog", "analytics")
