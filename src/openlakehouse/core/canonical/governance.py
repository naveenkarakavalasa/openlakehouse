"""Canonical Governance Model — formal representation of the OpenLakehouse
access-control concepts.

These models make the policy semantics explicit for the scholarly paper:
default-deny, last-match-wins, browse vs. query separation, and structured
authorization decisions with reason codes.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CanonicalEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class CanonicalPermission(str, Enum):
    """Coarse-grained capability granted to a role.

    BROWSE covers list_catalogs / list_schemas / list_tables / describe_table.
    QUERY covers run_query (execute SQL).
    """

    BROWSE = "browse"
    QUERY = "query"


class CanonicalResourceScope(BaseModel):
    """4-segment resource address. '*' is a wildcard at any segment."""

    model_config = ConfigDict(populate_by_name=True)

    adapter: str = "*"
    catalog: str = "*"
    schema: str = "*"
    table: str = "*"

    def __str__(self) -> str:
        return f"{self.adapter}/{self.catalog}/{self.schema}/{self.table}"


class CanonicalPolicyRule(BaseModel):
    """One allow/deny rule matched against a resource scope."""

    effect: CanonicalEffect
    scope: CanonicalResourceScope
    description: str | None = None


class CanonicalRole(BaseModel):
    """A named set of policy rules plus permission flags."""

    name: str
    rules: list[CanonicalPolicyRule]
    permissions: set[CanonicalPermission] = Field(
        default_factory=lambda: {CanonicalPermission.BROWSE, CanonicalPermission.QUERY}
    )


class CanonicalIdentity(BaseModel):
    """Maps a resolved identity string to a role name."""

    identity: str
    role_name: str


class CanonicalPolicy(BaseModel):
    """Full governance policy document in canonical form."""

    identities: dict[str, str]
    roles: dict[str, CanonicalRole]
    default_role: str | None = None


class CanonicalReasonCode(str, Enum):
    """Machine-readable reason code for an authorization decision."""

    ALLOWED = "ALLOWED"
    DENIED_BY_RULE = "DENIED_BY_RULE"
    DENIED_NO_MATCHING_RULE = "DENIED_NO_MATCHING_RULE"
    DENIED_NO_ROLE = "DENIED_NO_ROLE"
    DENIED_NO_QUERY_PERMISSION = "DENIED_NO_QUERY_PERMISSION"


class CanonicalAuthorizationDecision(BaseModel):
    """Structured output of a single authorization check.

    Carrying a decision object (rather than just raising an exception) makes
    the governance logic introspectable for the evaluation/governance_matrix
    module and for paper experiments.
    """

    allowed: bool
    effect: CanonicalEffect
    identity: str
    role: str | None
    resource: CanonicalResourceScope
    reason: str
    reason_code: CanonicalReasonCode
