import time

import boto3
from botocore.exceptions import ClientError

from openlakehouse.core.adapter import LakehouseAdapter
from openlakehouse.core.errors import PermissionDeniedError, QueryExecutionError, TableNotFoundError
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
from openlakehouse.core.sql_guard import assert_read_only

_GLUE_TYPE_MAP = {
    "string": ColumnType.STRING,
    "int": ColumnType.INTEGER,
    "bigint": ColumnType.BIGINT,
    "float": ColumnType.FLOAT,
    "double": ColumnType.DOUBLE,
    "boolean": ColumnType.BOOLEAN,
    "date": ColumnType.DATE,
    "timestamp": ColumnType.TIMESTAMP,
    "decimal": ColumnType.DECIMAL,
    "binary": ColumnType.BINARY,
}


def _map_glue_type(raw: str) -> ColumnType:
    base = raw.split("(")[0].split("<")[0].lower()
    if base == "array":
        return ColumnType.ARRAY
    if base == "map":
        return ColumnType.MAP
    if base == "struct":
        return ColumnType.STRUCT
    return _GLUE_TYPE_MAP.get(base, ColumnType.UNKNOWN)


class AWSAdapter(LakehouseAdapter):
    """Adapter for AWS Glue Data Catalog (metadata) + Athena (query execution).

    AWS has no native multi-catalog concept like Unity Catalog: there is one
    Glue Data Catalog per account+region. We map the Glue Data Catalog itself
    to our "catalog" concept (named from config, default "AwsDataCatalog" —
    Athena's own convention) and Glue databases to our "schema" concept, which
    keeps TableRef uniform across both adapters.
    """

    def __init__(
        self,
        name: str,
        *,
        region: str,
        catalog_name: str = "AwsDataCatalog",
        athena_output_location: str,
        athena_workgroup: str | None = None,
        profile: str | None = None,
        poll_interval_seconds: float = 1.0,
        poll_timeout_seconds: float = 120.0,
    ) -> None:
        self.name = name
        self._catalog_name = catalog_name
        self._output_location = athena_output_location
        self._workgroup = athena_workgroup
        self._poll_interval = poll_interval_seconds
        self._poll_timeout = poll_timeout_seconds

        session = boto3.Session(profile_name=profile, region_name=region)
        self._glue = session.client("glue")
        self._athena = session.client("athena")

    def list_catalogs(self) -> list[CatalogRef]:
        return [CatalogRef(adapter=self.name, catalog=self._catalog_name)]

    def list_schemas(self, catalog: str) -> list[SchemaRef]:
        schemas: list[SchemaRef] = []
        try:
            paginator = self._glue.get_paginator("get_databases")
            for page in paginator.paginate():
                for db in page["DatabaseList"]:
                    schemas.append(SchemaRef(adapter=self.name, catalog=catalog, schema=db["Name"]))
        except ClientError as exc:
            raise self._map_client_error(exc) from exc
        return schemas

    def list_tables(self, catalog: str, schema: str) -> list[TableSummary]:
        tables: list[TableSummary] = []
        try:
            paginator = self._glue.get_paginator("get_tables")
            for page in paginator.paginate(DatabaseName=schema):
                for t in page["TableList"]:
                    table_type = "VIEW" if t.get("TableType") == "VIRTUAL_VIEW" else "TABLE"
                    tables.append(
                        TableSummary(
                            table_ref=TableRef(adapter=self.name, catalog=catalog, schema=schema, table=t["Name"]),
                            table_type=table_type,
                            comment=t.get("Description"),
                        )
                    )
        except ClientError as exc:
            raise self._map_client_error(exc) from exc
        return tables

    def describe_table(self, catalog: str, schema: str, table: str) -> TableSchema:
        try:
            resp = self._glue.get_table(DatabaseName=schema, Name=table)
        except self._glue.exceptions.EntityNotFoundException as exc:
            raise TableNotFoundError(f"{catalog}.{schema}.{table}") from exc
        except ClientError as exc:
            raise self._map_client_error(exc) from exc

        table_def = resp["Table"]
        storage = table_def.get("StorageDescriptor", {})
        raw_columns = storage.get("Columns", [])
        partition_keys = table_def.get("PartitionKeys", [])

        columns = [
            ColumnSchema(
                name=c["Name"],
                type=_map_glue_type(c.get("Type", "")),
                raw_type=c.get("Type", ""),
                nullable=True,
                comment=c.get("Comment"),
                is_partition_key=False,
                ordinal_position=i,
            )
            for i, c in enumerate(raw_columns)
        ]
        partition_columns = [
            ColumnSchema(
                name=c["Name"],
                type=_map_glue_type(c.get("Type", "")),
                raw_type=c.get("Type", ""),
                nullable=True,
                comment=c.get("Comment"),
                is_partition_key=True,
                ordinal_position=len(columns) + i,
            )
            for i, c in enumerate(partition_keys)
        ]
        all_columns = columns + partition_columns

        return TableSchema(
            table_ref=TableRef(adapter=self.name, catalog=catalog, schema=schema, table=table),
            columns=all_columns,
            partition_columns=[c["Name"] for c in partition_keys],
            table_format=storage.get("InputFormat"),
            comment=table_def.get("Description"),
            properties=table_def.get("Parameters", {}),
        )

    def execute_query(
        self,
        sql: str,
        *,
        catalog: str | None = None,
        schema: str | None = None,
        max_rows: int = 1000,
        page_token: str | None = None,
    ) -> QueryResult:
        assert_read_only(sql)

        if page_token:
            # page_token encodes "<query_execution_id>:<athena_next_token>"
            query_execution_id, athena_next_token = page_token.split(":", 1)
            return self._fetch_page(query_execution_id, athena_next_token or None, max_rows)

        context = {"Catalog": catalog or self._catalog_name}
        if schema:
            context["Database"] = schema

        kwargs = dict(
            QueryString=sql,
            QueryExecutionContext=context,
            ResultConfiguration={"OutputLocation": self._output_location},
        )
        if self._workgroup:
            kwargs["WorkGroup"] = self._workgroup

        try:
            start = self._athena.start_query_execution(**kwargs)
            query_execution_id = start["QueryExecutionId"]
            self._wait_for_completion(query_execution_id)
            return self._fetch_page(query_execution_id, None, max_rows)
        except ClientError as exc:
            raise self._map_client_error(exc) from exc

    def _wait_for_completion(self, query_execution_id: str) -> None:
        deadline = time.monotonic() + self._poll_timeout
        while True:
            resp = self._athena.get_query_execution(QueryExecutionId=query_execution_id)
            state = resp["QueryExecution"]["Status"]["State"]
            if state == "SUCCEEDED":
                return
            if state in ("FAILED", "CANCELLED"):
                reason = resp["QueryExecution"]["Status"].get("StateChangeReason", "unknown")
                raise QueryExecutionError(f"Athena query {state}: {reason}")
            if time.monotonic() > deadline:
                raise QueryExecutionError(f"Athena query timed out after {self._poll_timeout}s")
            time.sleep(self._poll_interval)

    def _fetch_page(self, query_execution_id: str, next_token: str | None, max_rows: int) -> QueryResult:
        kwargs = {"QueryExecutionId": query_execution_id, "MaxResults": max_rows}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = self._athena.get_query_results(**kwargs)

        result_set = resp["ResultSet"]
        col_info = result_set["ResultSetMetadata"]["ColumnInfo"]
        columns = [
            ColumnSchema(name=c["Name"], type=_map_glue_type(c.get("Type", "")), raw_type=c.get("Type", ""))
            for c in col_info
        ]

        raw_rows = result_set["Rows"]
        # The first page's first row (when fetched without a NextToken) is the
        # column-header row duplicated as data; subsequent pages don't repeat it.
        data_rows = raw_rows[1:] if next_token is None else raw_rows
        rows = [[cell.get("VarCharValue") for cell in r["Data"]] for r in data_rows]

        new_next_token = resp.get("NextToken")
        next_page_token = f"{query_execution_id}:{new_next_token}" if new_next_token else None

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=new_next_token is not None,
            next_page_token=next_page_token,
            query_id=query_execution_id,
        )

    @staticmethod
    def _map_client_error(exc: ClientError) -> Exception:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "AccessDeniedException":
            return PermissionDeniedError(str(exc))
        return QueryExecutionError(str(exc))
