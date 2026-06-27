import functools
import time

from mcp.server.fastmcp import FastMCP

from openlakehouse.core.canonical.mapper import (
    catalog_to_canonical,
    query_result_to_canonical,
    schema_to_canonical,
    table_schema_to_canonical,
    table_summary_to_canonical,
)
from openlakehouse.core.errors import OpenLakehouseError
from openlakehouse.server.context import ServerContext


def mcp_tool_errors(fn):
    """Turn OpenLakehouseError subclasses into a clean tool-error message.

    FastMCP surfaces a raised exception as a tool error result to the
    client; without this, a raw boto3/databricks-sdk traceback could leak
    internal details to the agent.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except OpenLakehouseError as exc:
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from None

    return wrapper


def register_tools(mcp: FastMCP, ctx: ServerContext) -> None:
    @mcp.tool()
    @mcp_tool_errors
    def list_catalogs() -> list[dict]:
        """List all catalogs across all configured lakehouse adapters that
        the current agent identity is authorized to see. Returns canonical
        catalog objects with adapter, platform, and catalog fields."""
        identity = ctx.identity_resolver.current_identity()
        all_catalogs = []
        for adapter in ctx.adapters.values():
            all_catalogs.extend(adapter.list_catalogs())
        visible = ctx.policy_engine.filter_catalogs(identity, all_catalogs)
        return [
            catalog_to_canonical(c, ctx.adapters[c.adapter].platform).model_dump()
            for c in visible
        ]

    @mcp.tool()
    @mcp_tool_errors
    def list_schemas(adapter: str, catalog: str) -> list[dict]:
        """List schemas (databases) within a catalog on a given adapter.
        Returns canonical schema objects including platform and native_schema."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog)
        adp = ctx.get_adapter(adapter)
        schemas = adp.list_schemas(catalog)
        visible = ctx.policy_engine.filter_schemas(identity, adapter, schemas)
        return [schema_to_canonical(s, adp.platform).model_dump() for s in visible]

    @mcp.tool()
    @mcp_tool_errors
    def list_tables(adapter: str, catalog: str, schema: str) -> list[dict]:
        """List tables and views within a schema. Returns canonical table
        objects with normalized table_type and platform metadata."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog, schema=schema)
        adp = ctx.get_adapter(adapter)
        tables = adp.list_tables(catalog, schema)
        visible = ctx.policy_engine.filter_tables(identity, adapter, catalog, schema, tables)
        return [table_summary_to_canonical(t, adp.platform).model_dump() for t in visible]

    @mcp.tool()
    @mcp_tool_errors
    def describe_table(adapter: str, catalog: str, schema: str, table: str) -> dict:
        """Get full column/type/partition schema for one table. Returns a
        canonical table schema with normalized CanonicalDataType per column."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(
            identity, adapter=adapter, catalog=catalog, schema=schema, table=table
        )
        adp = ctx.get_adapter(adapter)
        result = adp.describe_table(catalog, schema, table)
        return table_schema_to_canonical(result, adp.platform).model_dump()

    @mcp.tool()
    @mcp_tool_errors
    def run_query(
        adapter: str,
        sql: str,
        catalog: str | None = None,
        schema: str | None = None,
        max_rows: int = 1000,
        page_token: str | None = None,
    ) -> dict:
        """Execute a read-only SQL query (SELECT/WITH/SHOW/DESCRIBE/EXPLAIN
        only) against the given adapter and return one page of canonical
        results. Canonical output includes columns (with normalized data_type),
        rows, pagination (truncated, next_page_token, row_count), and execution
        metadata (query_id, adapter, platform, execution_time_ms).
        AWS/Athena supports real next-page pagination; Databricks narrows via
        LIMIT/WHERE (see pagination.truncated)."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(
            identity, adapter=adapter, catalog=catalog or "*", schema=schema, for_query=True
        )
        adp = ctx.get_adapter(adapter)
        t0 = time.monotonic()
        result = adp.execute_query(
            sql, catalog=catalog, schema=schema, max_rows=max_rows, page_token=page_token
        )
        elapsed_ms = (time.monotonic() - t0) * 1000
        return query_result_to_canonical(result, adapter, adp.platform, elapsed_ms).model_dump()
