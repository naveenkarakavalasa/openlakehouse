from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ColumnType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    BIGINT = "bigint"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    DECIMAL = "decimal"
    BINARY = "binary"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    UNKNOWN = "unknown"


class CatalogRef(BaseModel):
    adapter: str
    catalog: str


class SchemaRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    adapter: str
    catalog: str
    schema_name: str = Field(alias="schema")


class TableRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    adapter: str
    catalog: str
    schema_name: str = Field(alias="schema")
    table: str

    @property
    def qualified_name(self) -> str:
        return f"{self.catalog}.{self.schema_name}.{self.table}"


class ColumnSchema(BaseModel):
    name: str
    type: ColumnType
    raw_type: str
    nullable: bool = True
    comment: str | None = None
    is_partition_key: bool = False
    ordinal_position: int | None = None


class TableSchema(BaseModel):
    table_ref: TableRef
    columns: list[ColumnSchema]
    partition_columns: list[str] = Field(default_factory=list)
    table_format: str | None = None
    comment: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)


class TableSummary(BaseModel):
    """Lightweight entry for list_tables — no full column list."""

    table_ref: TableRef
    table_type: str = "TABLE"
    comment: str | None = None


class QueryResult(BaseModel):
    columns: list[ColumnSchema]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False
    next_page_token: str | None = None
    query_id: str | None = None
