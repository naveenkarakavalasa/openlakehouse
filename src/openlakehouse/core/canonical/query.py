"""Canonical Query Model — platform-agnostic query request and result structures.

Normalizes columns, rows, types, pagination, and execution metadata so that an
AI agent receives the same JSON shape regardless of whether the query ran on
Databricks SQL Warehouse or AWS Athena.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from openlakehouse.core.canonical.metadata import CanonicalDataType


class CanonicalQueryColumn(BaseModel):
    """A column in a query result with normalized data type."""

    name: str
    data_type: CanonicalDataType
    raw_type: str
    nullable: bool = True


class CanonicalPagination(BaseModel):
    """Pagination state for a query result page."""

    truncated: bool = False
    next_page_token: str | None = None
    row_count: int


class CanonicalExecutionMetadata(BaseModel):
    """Platform-specific execution details surfaced in a normalized envelope.

    native_metadata carries platform-specific extras without leaking them into
    the canonical fields — e.g. Athena WorkGroup, Databricks statement ID.
    """

    query_id: str | None = None
    adapter: str
    platform: str
    execution_time_ms: float | None = None
    native_metadata: dict[str, Any] = Field(default_factory=dict)


class CanonicalQueryResult(BaseModel):
    """Full canonical query result returned to AI agents via run_query."""

    columns: list[CanonicalQueryColumn]
    rows: list[list[Any]]
    pagination: CanonicalPagination
    execution: CanonicalExecutionMetadata


class CanonicalQueryRequest(BaseModel):
    """Structured representation of a run_query invocation."""

    model_config = ConfigDict(populate_by_name=True)

    adapter: str
    sql: str
    catalog: str | None = None
    schema: str | None = None
    max_rows: int = 1000
    page_token: str | None = None
