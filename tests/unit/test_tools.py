"""MCP tool layer tests.

Critical invariants verified here:
1. Policy is checked BEFORE the adapter is called — denied requests never touch the adapter.
2. Allowed requests return canonical model shapes (adapter, platform, canonical fields).
3. list_* tools silently filter out denied resources.
4. Unknown adapters raise a clean AdapterNotFoundError, not a raw exception.
"""
import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from openlakehouse.core.adapter import LakehouseAdapter
from openlakehouse.identity.resolver import IdentityResolver
from openlakehouse.policy.engine import PolicyEngine
from openlakehouse.policy.models import PolicyDocument, PolicyRule, Role
from openlakehouse.server.context import ServerContext
from openlakehouse.server.tools import register_tools


def _allow_policy() -> PolicyEngine:
    doc = PolicyDocument(
        identities={"test-bot": "analyst"},
        default_role=None,
        roles={
            "analyst": Role(
                name="analyst",
                rules=[PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")],
            )
        },
    )
    return PolicyEngine(doc)


def _deny_policy() -> PolicyEngine:
    doc = PolicyDocument(
        identities={"test-bot": "analyst"}, default_role=None, roles={"analyst": Role(name="analyst", rules=[])}
    )
    return PolicyEngine(doc)


def _build_ctx(mocker, policy_engine: PolicyEngine) -> tuple[ServerContext, LakehouseAdapter]:
    fake_adapter = mocker.Mock(spec=LakehouseAdapter)
    fake_adapter.name = "db1"
    fake_adapter.platform = "databricks"
    ctx = ServerContext(
        adapters={"db1": fake_adapter},
        policy_engine=policy_engine,
        identity_resolver=IdentityResolver(identity="test-bot"),
    )
    return ctx, fake_adapter


def _call_tool(mcp: FastMCP, name: str, arguments: dict):
    async def _run():
        return await mcp.call_tool(name, arguments)

    return asyncio.run(_run())


def _as_json(call_tool_result):
    if isinstance(call_tool_result, tuple):
        _, structured = call_tool_result
        return structured.get("result", structured)
    return json.loads(call_tool_result[0].text)


# ---------------------------------------------------------------------------
# Policy-before-adapter invariant tests
# ---------------------------------------------------------------------------

def test_list_schemas_denied_never_calls_adapter(mocker):
    ctx, fake_adapter = _build_ctx(mocker, _deny_policy())
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    with pytest.raises(ToolError, match="PermissionDeniedError"):
        _call_tool(mcp, "list_schemas", {"adapter": "db1", "catalog": "sales"})

    fake_adapter.list_schemas.assert_not_called()


def test_describe_table_denied_never_calls_adapter(mocker):
    ctx, fake_adapter = _build_ctx(mocker, _deny_policy())
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    with pytest.raises(ToolError, match="PermissionDeniedError"):
        _call_tool(
            mcp, "describe_table", {"adapter": "db1", "catalog": "sales", "schema": "public", "table": "orders"}
        )

    fake_adapter.describe_table.assert_not_called()


def test_run_query_denied_never_calls_adapter(mocker):
    ctx, fake_adapter = _build_ctx(mocker, _deny_policy())
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    with pytest.raises(ToolError, match="PermissionDeniedError"):
        _call_tool(mcp, "run_query", {"adapter": "db1", "sql": "SELECT 1"})

    fake_adapter.execute_query.assert_not_called()


# ---------------------------------------------------------------------------
# Canonical response shape tests
# ---------------------------------------------------------------------------

def test_list_catalogs_returns_canonical_shape(mocker):
    from openlakehouse.core.models import CatalogRef

    ctx, fake_adapter = _build_ctx(mocker, _allow_policy())
    fake_adapter.list_catalogs.return_value = [CatalogRef(adapter="db1", catalog="sales")]
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "list_catalogs", {})
    result = _as_json(content)

    assert len(result) == 1
    cat = result[0]
    assert cat["adapter"] == "db1"
    assert cat["platform"] == "databricks"
    assert cat["catalog"] == "sales"
    assert cat["native_catalog"] == "sales"


def test_list_schemas_returns_canonical_shape(mocker):
    from openlakehouse.core.models import SchemaRef

    ctx, fake_adapter = _build_ctx(mocker, _allow_policy())
    fake_adapter.list_schemas.return_value = [SchemaRef(adapter="db1", catalog="sales", schema="public")]
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "list_schemas", {"adapter": "db1", "catalog": "sales"})
    result = _as_json(content)

    assert len(result) == 1
    s = result[0]
    assert s["adapter"] == "db1"
    assert s["platform"] == "databricks"
    assert s["catalog"] == "sales"
    assert s["schema"] == "public"
    assert s["native_schema"] == "public"


def test_list_tables_returns_canonical_shape(mocker):
    from openlakehouse.core.models import TableRef, TableSummary

    ctx, fake_adapter = _build_ctx(mocker, _allow_policy())
    fake_adapter.list_tables.return_value = [
        TableSummary(table_ref=TableRef(adapter="db1", catalog="sales", schema="public", table="orders"))
    ]
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "list_tables", {"adapter": "db1", "catalog": "sales", "schema": "public"})
    result = _as_json(content)

    assert len(result) == 1
    t = result[0]
    assert t["adapter"] == "db1"
    assert t["platform"] == "databricks"
    assert t["catalog"] == "sales"
    assert t["schema"] == "public"
    assert t["table"] == "orders"
    assert t["table_type"] == "TABLE"


def test_run_query_returns_canonical_shape(mocker):
    from openlakehouse.core.models import ColumnSchema, ColumnType, QueryResult

    ctx, fake_adapter = _build_ctx(mocker, _allow_policy())
    fake_adapter.execute_query.return_value = QueryResult(
        columns=[ColumnSchema(name="n", type=ColumnType.INTEGER, raw_type="integer")],
        rows=[[1]],
        row_count=1,
        truncated=False,
        query_id="q-123",
    )
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "run_query", {"adapter": "db1", "sql": "SELECT 1 AS n"})
    result = _as_json(content)

    assert result["columns"][0]["name"] == "n"
    assert result["columns"][0]["data_type"] == "integer"
    assert result["rows"] == [[1]]
    assert result["pagination"]["row_count"] == 1
    assert result["pagination"]["truncated"] is False
    assert result["execution"]["adapter"] == "db1"
    assert result["execution"]["platform"] == "databricks"
    assert result["execution"]["query_id"] == "q-123"
    assert result["execution"]["execution_time_ms"] is not None


# ---------------------------------------------------------------------------
# Filter invariant tests
# ---------------------------------------------------------------------------

def test_list_tables_filters_out_denied_table(mocker):
    from openlakehouse.core.models import TableRef, TableSummary

    doc = PolicyDocument(
        identities={"test-bot": "analyst"},
        default_role=None,
        roles={
            "analyst": Role(
                name="analyst",
                rules=[
                    PolicyRule(effect="allow", adapter="db1", catalog="sales", schema_name="public", table="*"),
                    PolicyRule(effect="deny", adapter="db1", catalog="sales", schema_name="public", table="ssn"),
                ],
            )
        },
    )
    ctx, fake_adapter = _build_ctx(mocker, PolicyEngine(doc))
    fake_adapter.list_tables.return_value = [
        TableSummary(table_ref=TableRef(adapter="db1", catalog="sales", schema="public", table="orders")),
        TableSummary(table_ref=TableRef(adapter="db1", catalog="sales", schema="public", table="ssn")),
    ]
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "list_tables", {"adapter": "db1", "catalog": "sales", "schema": "public"})
    tables = _as_json(content)

    assert [t["table"] for t in tables] == ["orders"]


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

def test_unknown_adapter_raises_clean_error_not_traceback(mocker):
    ctx, _ = _build_ctx(mocker, _allow_policy())
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    with pytest.raises(ToolError, match="AdapterNotFoundError"):
        _call_tool(mcp, "list_schemas", {"adapter": "does-not-exist", "catalog": "sales"})
