import os

from openlakehouse.server.app import build_server


def main() -> None:
    config_path = os.environ.get("OPENLAKEHOUSE_CONFIG", "config/config.yaml")
    mcp = build_server(config_path)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
