import os

from openlakehouse.core.errors import IdentityResolutionError


class IdentityResolver:
    """Resolves a static agent identity for this server process.

    v1: identity is fixed for the lifetime of the process, taken from an
    environment variable set in the MCP client's server launch config.
    This matches the MCP stdio transport, which has no per-request auth
    channel — every tool call within one server process is the same
    "agent" for policy purposes. Whoever controls the server's launch
    config controls its identity, same as any other locally-configured
    credential; this is the documented v1 trust boundary.
    """

    ENV_VAR = "OPENLAKEHOUSE_IDENTITY"

    def __init__(self, identity: str | None = None) -> None:
        self._identity = identity or os.environ.get(self.ENV_VAR)
        if not self._identity:
            raise IdentityResolutionError(
                f"{self.ENV_VAR} is not set. Every OpenLakehouse MCP server "
                "process must be launched with an identity configured."
            )

    def current_identity(self) -> str:
        return self._identity
