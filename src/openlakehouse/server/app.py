from mcp.server.fastmcp import FastMCP

from openlakehouse.adapters.registry import build_adapter
from openlakehouse.config.loader import load_config
from openlakehouse.identity.resolver import IdentityResolver
from openlakehouse.policy.engine import PolicyEngine
from openlakehouse.policy.loader import load_policy
from openlakehouse.server.context import ServerContext
from openlakehouse.server.tools import register_tools


def build_server(config_path: str = "config/config.yaml") -> FastMCP:
    app_config = load_config(config_path)
    policy_doc = load_policy(app_config.policy_path)

    adapters = {name: build_adapter(name, cfg) for name, cfg in app_config.adapters.items()}
    ctx = ServerContext(
        adapters=adapters,
        policy_engine=PolicyEngine(policy_doc),
        identity_resolver=IdentityResolver(),
    )

    mcp = FastMCP("OpenLakehouse")
    register_tools(mcp, ctx)
    return mcp
