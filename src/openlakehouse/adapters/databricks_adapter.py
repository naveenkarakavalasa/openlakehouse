from databricks import sql as databricks_sql
from databricks.sdk import WorkspaceClient

from openlakehouse.core.adapter import LakehouseAdapter
from openlakehouse.core.errors import QueryExecutionError, TableNotFoundError
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

_TYPE_MAP = {
    "STRING": ColumnType.STRING,
    "INT": ColumnType.INTEGER,
    "SHORT": ColumnType.INTEGER,
    "LONG": ColumnType.BIGINT,
    "FLOAT": ColumnType.FLOAT,
    "DOUBLE": ColumnType.DOUBLE,
    "BOOLEAN": ColumnType.BOOLEAN,
    "DATE": ColumnType.DATE,
    "TIMESTAMP": ColumnType.TIMESTAMP,
    "TIMESTAMP_NTZ": ColumnType.TIMESTAMP,
    "DECIMAL": ColumnType.DECIMAL,
    "BINARY": ColumnType.BINARY,
    "ARRAY": ColumnType.ARRAY,
    "MAP": ColumnType.MAP,
    "STRUCT": ColumnType.STRUCT,
}


class DatabricksAdapter(LakehouseAdapter):
    """Adapter for Databricks Unity Catalog (metadata) + SQL Warehouse (queries).

    Metadata goes through `databricks-sdk`'s typed Unity Catalog API rather
    than SQL (`SHOW TABLES`) — more reliable, structured types, built-in
    pagination/retries. Query execution goes through the separate
    `databricks-sql-connector` DB-API driver against a SQL Warehouse.
    """

    def __init__(
        self,
        name: str,
        *,
        host: str,
        token: str,
        warehouse_http_path: str,
    ) -> None:
        self.name = name
        self._host = host
        self._warehouse_http_path = warehouse_http_path
        self._token = token
        self._workspace = WorkspaceClient(host=host, token=token)

    def list_catalogs(self) -> list[CatalogRef]:
        return [CatalogRef(adapter=self.name, catalog=c.name) for c in self._workspace.catalogs.list()]

    def list_schemas(self, catalog: str) -> list[SchemaRef]:
        return [
            SchemaRef(adapter=self.name, catalog=catalog, schema=s.name)
            for s in self._workspace.schemas.list(catalog_name=catalog)
        ]

    def list_tables(self, catalog: str, schema: str) -> list[TableSummary]:
        tables = self._workspace.tables.list(catalog_name=catalog, schema_name=schema)
        return [
            TableSummary(
                table_ref=TableRef(adapter=self.name, catalog=catalog, schema=schema, table=t.name),
                table_type="VIEW" if t.table_type and "VIEW" in t.table_type.value else "TABLE",
                comment=t.comment,
            )
            for t in tables
        ]

    def describe_table(self, catalog: str, schema: str, table: str) -> TableSchema:
        full_name = f"{catalog}.{schema}.{table}"
        try:
            info = self._workspace.tables.get(full_name=full_name)
        except Exception as exc:
            raise TableNotFoundError(full_name) from exc

        columns = [
            ColumnSchema(
                name=col.name,
                type=_TYPE_MAP.get((col.type_name.value if col.type_name else ""), ColumnType.UNKNOWN),
                raw_type=col.type_text or "",
                nullable=col.nullable if col.nullable is not None else True,
                comment=col.comment,
                is_partition_key=(col.partition_index is not None),
                ordinal_position=col.position,
            )
            for col in (info.columns or [])
        ]
        partition_cols = [c.name for c in columns if c.is_partition_key]

        return TableSchema(
            table_ref=TableRef(adapter=self.name, catalog=catalog, schema=schema, table=table),
            columns=columns,
            partition_columns=partition_cols,
            table_format=info.data_source_format.value if info.data_source_format else None,
            comment=info.comment,
            properties=info.properties or {},
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
        try:
            with databricks_sql.connect(
                server_hostname=self._host.replace("https://", "").replace("http://", ""),
                http_path=self._warehouse_http_path,
                access_token=self._token,
                catalog=catalog,
                schema=schema,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    desc = cursor.description or []
                    columns = [
                        ColumnSchema(
                            name=d[0],
                            type=_TYPE_MAP.get(str(d[1]).upper(), ColumnType.UNKNOWN),
                            raw_type=str(d[1]),
                        )
                        for d in desc
                    ]
                    rows = cursor.fetchmany(max_rows)
                    extra = cursor.fetchone()  # peek: is there more?
                    truncated = extra is not None
                    return QueryResult(
                        columns=columns,
                        rows=[list(r) for r in rows],
                        row_count=len(rows),
                        truncated=truncated,
                        next_page_token=None,
                        query_id=None,
                    )
        except Exception as exc:
            raise QueryExecutionError(str(exc)) from exc
