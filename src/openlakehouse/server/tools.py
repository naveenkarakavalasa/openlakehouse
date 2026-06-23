import functools

from mcp.server.fastmcp import FastMCP

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
        the current agent identity is authorized to see."""
        identity = ctx.identity_resolver.current_identity()
        all_catalogs = []
        for adapter in ctx.adapters.values():
            all_catalogs.extend(adapter.list_catalogs())
        visible = ctx.policy_engine.filter_catalogs(identity, all_catalogs)
        return [c.model_dump() for c in visible]

    @mcp.tool()
    @mcp_tool_errors
    def list_schemas(adapter: str, catalog: str) -> list[dict]:
        """List schemas (databases) within a catalog on a given adapter."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog)
        schemas = ctx.get_adapter(adapter).list_schemas(catalog)
        visible = ctx.policy_engine.filter_schemas(identity, adapter, schemas)
        return [s.model_dump(by_alias=True) for s in visible]

    @mcp.tool()
    @mcp_tool_errors
    def list_tables(adapter: str, catalog: str, schema: str) -> list[dict]:
        """List tables and views within a schema."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog, schema=schema)
        tables = ctx.get_adapter(adapter).list_tables(catalog, schema)
        visible = ctx.policy_engine.filter_tables(identity, adapter, catalog, schema, tables)
        return [t.model_dump(by_alias=True) for t in visible]

    @mcp.tool()
    @mcp_tool_errors
    def describe_table(adapter: str, catalog: str, schema: str, table: str) -> dict:
        """Get full column/type/partition schema for one table."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog, schema=schema, table=table)
        result = ctx.get_adapter(adapter).describe_table(catalog, schema, table)
        return result.model_dump(by_alias=True)

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
        only) against the given adapter and return one page of results.
        If the result is truncated, call again with the returned
        next_page_token to fetch the next page (supported for the AWS
        adapter; the Databricks adapter narrows via LIMIT/WHERE instead —
        see the truncated flag)."""
        identity = ctx.identity_resolver.current_identity()
        ctx.policy_engine.authorize(
            identity, adapter=adapter, catalog=catalog or "*", schema=schema, for_query=True
        )
        result = ctx.get_adapter(adapter).execute_query(
            sql, catalog=catalog, schema=schema, max_rows=max_rows, page_token=page_token
        )
        return result.model_dump()
