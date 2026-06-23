class OpenLakehouseError(Exception):
    """Base class for all OpenLakehouse errors surfaced to MCP tool callers."""


class AdapterNotFoundError(OpenLakehouseError):
    pass


class PermissionDeniedError(OpenLakehouseError):
    """Raised by the policy engine; must map to a clear MCP tool error, never a stack trace."""


class TableNotFoundError(OpenLakehouseError):
    pass


class QueryExecutionError(OpenLakehouseError):
    pass


class IdentityResolutionError(OpenLakehouseError):
    pass
