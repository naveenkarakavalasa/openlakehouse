import os

from openlakehouse.server.app import build_server

if __name__ == "__main__":
    config_path = os.environ.get("OPENLAKEHOUSE_CONFIG", "config/config.yaml")
    mcp = build_server(config_path)
    mcp.run(transport="stdio")
