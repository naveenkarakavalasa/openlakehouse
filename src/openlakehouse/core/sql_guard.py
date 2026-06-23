import re

_ALLOWED_PREFIXES = ("select", "with", "show", "describe", "explain")
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|merge|grant|revoke)\b",
    re.IGNORECASE,
)


class UnsafeQueryError(ValueError):
    pass


def assert_read_only(sql: str) -> None:
    """Reject SQL that isn't a read-only statement.

    This is a denylist/allowlist hybrid, not a full SQL parser — a CTE
    literally named e.g. `with updated as (...)` could false-positive on
    the forbidden-keyword check. Acceptable v1 tradeoff; adapters should
    additionally run with read-only platform grants where possible.
    """
    stripped = sql.strip().lower()
    if not stripped.startswith(_ALLOWED_PREFIXES):
        raise UnsafeQueryError(f"Query must start with one of {_ALLOWED_PREFIXES}")
    if _FORBIDDEN_PATTERN.search(sql):
        raise UnsafeQueryError("Query contains a forbidden write/DDL keyword")
