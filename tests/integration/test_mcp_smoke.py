import asyncio

from openlakehouse.server.app import build_server

CONFIG_YAML = """
policy_path: {policy_path}
adapters:
  aws_test:
    type: aws
    region: us-east-1
    athena_output_location: s3://my-bucket/athena-results/
"""

POLICY_YAML = """
identities:
  test-identity: admin
default_role: null
roles:
  admin:
    can_execute_queries: true
    rules:
      - effect: allow
        adapter: "*"
        catalog: "*"
        schema: "*"
        table: "*"
"""


def test_build_server_wires_config_policy_and_adapters_and_exposes_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENLAKEHOUSE_IDENTITY", "test-identity")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(POLICY_YAML)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(CONFIG_YAML.format(policy_path=policy_path))

    mcp = build_server(str(config_path))

    async def _list_tool_names():
        tools = await mcp.list_tools()
        return sorted(t.name for t in tools)

    tool_names = asyncio.run(_list_tool_names())
    assert tool_names == ["describe_table", "list_catalogs", "list_schemas", "list_tables", "run_query"]
