"""Mapping functions from internal adapter models to canonical models.

All conversions are pure functions with no side effects. The mapper is the
only place that knows about both the internal models (core/models.py) and
the canonical models — adapters and tools import from here, not from each other.
"""
from __future__ import annotations

from openlakehouse.core.models import (
    CatalogRef,
    ColumnSchema,
    ColumnType,
    QueryResult,
    SchemaRef,
    TableSchema,
    TableSummary,
)

from openlakehouse.core.canonical.metadata import (
    CanonicalCatalog,
    CanonicalColumn,
    CanonicalDataType,
    CanonicalSchema,
    CanonicalTable,
    CanonicalTableSchema,
    CanonicalTableType,
)
from openlakehouse.core.canonical.query import (
    CanonicalExecutionMetadata,
    CanonicalPagination,
    CanonicalQueryColumn,
    CanonicalQueryResult,
)

_COLUMN_TYPE_MAP: dict[ColumnType, CanonicalDataType] = {
    ColumnType.STRING: CanonicalDataType.STRING,
    ColumnType.INTEGER: CanonicalDataType.INTEGER,
    ColumnType.BIGINT: CanonicalDataType.BIGINT,
    ColumnType.FLOAT: CanonicalDataType.FLOAT,
    ColumnType.DOUBLE: CanonicalDataType.DOUBLE,
    ColumnType.BOOLEAN: CanonicalDataType.BOOLEAN,
    ColumnType.DATE: CanonicalDataType.DATE,
    ColumnType.TIMESTAMP: CanonicalDataType.TIMESTAMP,
    ColumnType.DECIMAL: CanonicalDataType.DECIMAL,
    ColumnType.BINARY: CanonicalDataType.BINARY,
    ColumnType.ARRAY: CanonicalDataType.ARRAY,
    ColumnType.MAP: CanonicalDataType.MAP,
    ColumnType.STRUCT: CanonicalDataType.STRUCT,
    ColumnType.UNKNOWN: CanonicalDataType.UNKNOWN,
}


def _to_data_type(ct: ColumnType) -> CanonicalDataType:
    return _COLUMN_TYPE_MAP.get(ct, CanonicalDataType.UNKNOWN)


def catalog_to_canonical(ref: CatalogRef, platform: str) -> CanonicalCatalog:
    return CanonicalCatalog(
        adapter=ref.adapter,
        platform=platform,
        catalog=ref.catalog,
        native_catalog=ref.catalog,
    )


def schema_to_canonical(ref: SchemaRef, platform: str) -> CanonicalSchema:
    return CanonicalSchema(
        adapter=ref.adapter,
        platform=platform,
        catalog=ref.catalog,
        schema=ref.schema_name,
        native_schema=ref.schema_name,
    )


def table_summary_to_canonical(t: TableSummary, platform: str) -> CanonicalTable:
    ttype = CanonicalTableType.VIEW if t.table_type == "VIEW" else CanonicalTableType.TABLE
    return CanonicalTable(
        adapter=t.table_ref.adapter,
        platform=platform,
        catalog=t.table_ref.catalog,
        schema=t.table_ref.schema_name,
        table=t.table_ref.table,
        table_type=ttype,
        comment=t.comment,
    )


def column_to_canonical(col: ColumnSchema) -> CanonicalColumn:
    return CanonicalColumn(
        name=col.name,
        data_type=_to_data_type(col.type),
        raw_type=col.raw_type,
        nullable=col.nullable,
        comment=col.comment,
        is_partition_key=col.is_partition_key,
        ordinal_position=col.ordinal_position,
    )


def table_schema_to_canonical(ts: TableSchema, platform: str) -> CanonicalTableSchema:
    return CanonicalTableSchema(
        table=CanonicalTable(
            adapter=ts.table_ref.adapter,
            platform=platform,
            catalog=ts.table_ref.catalog,
            schema=ts.table_ref.schema_name,
            table=ts.table_ref.table,
            comment=ts.comment,
        ),
        columns=[column_to_canonical(c) for c in ts.columns],
        partition_columns=ts.partition_columns,
        table_format=ts.table_format,
        comment=ts.comment,
        properties=ts.properties,
    )


def query_result_to_canonical(
    qr: QueryResult,
    adapter: str,
    platform: str,
    execution_time_ms: float | None = None,
) -> CanonicalQueryResult:
    return CanonicalQueryResult(
        columns=[
            CanonicalQueryColumn(
                name=c.name,
                data_type=_to_data_type(c.type),
                raw_type=c.raw_type,
                nullable=c.nullable,
            )
            for c in qr.columns
        ],
        rows=qr.rows,
        pagination=CanonicalPagination(
            truncated=qr.truncated,
            next_page_token=qr.next_page_token,
            row_count=qr.row_count,
        ),
        execution=CanonicalExecutionMetadata(
            query_id=qr.query_id,
            adapter=adapter,
            platform=platform,
            execution_time_ms=execution_time_ms,
        ),
    )
