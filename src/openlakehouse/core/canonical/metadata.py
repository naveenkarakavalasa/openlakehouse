"""Canonical Metadata Model — platform-agnostic representations of lakehouse
catalog/schema/table/column concepts.

Every platform adapter maps its native identifiers into these models so that AI
agents receive a uniform structure regardless of whether data lives in Databricks
Unity Catalog or AWS Glue Data Catalog.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CanonicalDataType(str, Enum):
    """Normalized column data type vocabulary shared across all platforms."""

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


class CanonicalTableType(str, Enum):
    TABLE = "TABLE"
    VIEW = "VIEW"
    EXTERNAL = "EXTERNAL"
    MANAGED = "MANAGED"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW"


class PlatformNamespaceMapping(BaseModel):
    """Documents how a platform's native namespace maps to the canonical
    3-level catalog.schema.table hierarchy."""

    platform: str
    catalog_concept: str
    schema_concept: str
    table_concept: str
    notes: str | None = None


DATABRICKS_NAMESPACE = PlatformNamespaceMapping(
    platform="databricks",
    catalog_concept="Unity Catalog",
    schema_concept="Schema",
    table_concept="Table / View",
    notes="Native 3-level namespace: catalog.schema.table. Metadata via databricks-sdk WorkspaceClient; queries via SQL Warehouse.",
)

AWS_NAMESPACE = PlatformNamespaceMapping(
    platform="aws",
    catalog_concept="Glue Data Catalog (mapped as AwsDataCatalog)",
    schema_concept="Glue Database",
    table_concept="Glue Table",
    notes="AWS has no native catalog tier; the Glue Data Catalog is mapped as the catalog (AwsDataCatalog). Metadata via boto3 Glue; queries via Athena.",
)


class CanonicalCatalog(BaseModel):
    """Canonical representation of a catalog — top level of the 3-level namespace."""

    adapter: str
    platform: str
    catalog: str
    native_catalog: str
    comment: str | None = None
    platform_metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalSchema(BaseModel):
    """Canonical representation of a schema (database) within a catalog."""

    model_config = ConfigDict(populate_by_name=True)

    adapter: str
    platform: str
    catalog: str
    schema: str
    native_schema: str
    comment: str | None = None
    platform_metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalTable(BaseModel):
    """Canonical representation of a table or view."""

    model_config = ConfigDict(populate_by_name=True)

    adapter: str
    platform: str
    catalog: str
    schema: str
    table: str
    table_type: CanonicalTableType = CanonicalTableType.TABLE
    comment: str | None = None
    platform_metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalColumn(BaseModel):
    """Canonical representation of a table column with normalized type."""

    name: str
    data_type: CanonicalDataType
    raw_type: str
    nullable: bool = True
    comment: str | None = None
    is_partition_key: bool = False
    ordinal_position: int | None = None


class CanonicalTableSchema(BaseModel):
    """Full schema of a table including all columns and metadata."""

    table: CanonicalTable
    columns: list[CanonicalColumn]
    partition_columns: list[str] = Field(default_factory=list)
    table_format: str | None = None
    comment: str | None = None
    properties: dict[str, str] = Field(default_factory=dict)
