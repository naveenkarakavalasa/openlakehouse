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
    # FastMCP.call_tool returns (content_blocks, structured_content) for
    # tools with a structured (non-string) return type.
    if isinstance(call_tool_result, tuple):
        _, structured = call_tool_result
        return structured.get("result", structured)
    return json.loads(call_tool_result[0].text)


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


def test_list_schemas_allowed_calls_adapter_and_returns_data(mocker):
    from openlakehouse.core.models import SchemaRef

    ctx, fake_adapter = _build_ctx(mocker, _allow_policy())
    fake_adapter.list_schemas.return_value = [SchemaRef(adapter="db1", catalog="sales", schema="public")]
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    content = _call_tool(mcp, "list_schemas", {"adapter": "db1", "catalog": "sales"})

    fake_adapter.list_schemas.assert_called_once_with("sales")
    assert _as_json(content) == [{"adapter": "db1", "catalog": "sales", "schema": "public"}]


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

    assert [t["table_ref"]["table"] for t in tables] == ["orders"]


def test_unknown_adapter_raises_clean_error_not_traceback(mocker):
    ctx, _ = _build_ctx(mocker, _allow_policy())
    mcp = FastMCP("test")
    register_tools(mcp, ctx)

    with pytest.raises(ToolError, match="AdapterNotFoundError"):
        _call_tool(mcp, "list_schemas", {"adapter": "does-not-exist", "catalog": "sales"})
