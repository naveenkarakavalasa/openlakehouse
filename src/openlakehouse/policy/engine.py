from openlakehouse.core.canonical.governance import (
    CanonicalAuthorizationDecision,
    CanonicalEffect,
    CanonicalPermission,
    CanonicalReasonCode,
    CanonicalResourceScope,
)
from openlakehouse.core.errors import PermissionDeniedError
from openlakehouse.policy.models import PolicyDocument, Role


class PolicyEngine:
    """Single choke point for all access-control decisions.

    Default-deny: no matching rule means denied. Rules within a role are
    evaluated in list order with last-match-wins, so an admin can write
    `allow catalog=sales` followed by `deny schema=sales.pii` as two
    readable lines without needing rule-priority bookkeeping.
    """

    def __init__(self, document: PolicyDocument) -> None:
        self._doc = document

    def _role_for(self, identity: str) -> Role | None:
        role_name = self._doc.identities.get(identity, self._doc.default_role)
        if role_name is None:
            return None
        return self._doc.roles.get(role_name)

    def authorize(
        self,
        identity: str,
        *,
        adapter: str,
        catalog: str,
        schema: str | None = None,
        table: str | None = None,
        for_query: bool = False,
    ) -> None:
        """Raise PermissionDeniedError if `identity` may not access this resource."""
        role = self._role_for(identity)
        if role is None:
            raise PermissionDeniedError(f"Identity '{identity}' has no assigned role")

        if for_query and not role.can_execute_queries:
            raise PermissionDeniedError(f"Role '{role.name}' is not permitted to execute queries")

        decision = "deny"
        for rule in role.rules:
            if rule.matches(adapter, catalog, schema, table):
                decision = rule.effect

        if decision != "allow":
            target = ".".join(filter(None, [adapter, catalog, schema, table]))
            raise PermissionDeniedError(
                f"Identity '{identity}' (role '{role.name}') denied access to {target}"
            )

    def _is_allowed(
        self,
        identity: str,
        adapter: str,
        catalog: str,
        schema: str | None = None,
        table: str | None = None,
    ) -> bool:
        try:
            self.authorize(identity, adapter=adapter, catalog=catalog, schema=schema, table=table)
            return True
        except PermissionDeniedError:
            return False

    def authorize_with_decision(
        self,
        identity: str,
        *,
        adapter: str,
        catalog: str,
        schema: str | None = None,
        table: str | None = None,
        for_query: bool = False,
    ) -> CanonicalAuthorizationDecision:
        """Return a structured authorization decision without raising.

        Use this for introspection and evaluation; use authorize() in tool
        code where a PermissionDeniedError should halt execution immediately.
        """
        resource = CanonicalResourceScope(
            adapter=adapter,
            catalog=catalog,
            schema=schema or "*",
            table=table or "*",
        )
        role = self._role_for(identity)
        if role is None:
            return CanonicalAuthorizationDecision(
                allowed=False,
                effect=CanonicalEffect.DENY,
                identity=identity,
                role=None,
                resource=resource,
                reason=f"Identity '{identity}' has no assigned role",
                reason_code=CanonicalReasonCode.DENIED_NO_ROLE,
            )

        if for_query and not role.can_execute_queries:
            return CanonicalAuthorizationDecision(
                allowed=False,
                effect=CanonicalEffect.DENY,
                identity=identity,
                role=role.name,
                resource=resource,
                reason=f"Role '{role.name}' does not have {CanonicalPermission.QUERY} permission",
                reason_code=CanonicalReasonCode.DENIED_NO_QUERY_PERMISSION,
            )

        matched_effect: str | None = None
        for rule in role.rules:
            if rule.matches(adapter, catalog, schema, table):
                matched_effect = rule.effect

        if matched_effect is None:
            return CanonicalAuthorizationDecision(
                allowed=False,
                effect=CanonicalEffect.DENY,
                identity=identity,
                role=role.name,
                resource=resource,
                reason=f"No matching rule for {resource}",
                reason_code=CanonicalReasonCode.DENIED_NO_MATCHING_RULE,
            )

        allowed = matched_effect == "allow"
        return CanonicalAuthorizationDecision(
            allowed=allowed,
            effect=CanonicalEffect.ALLOW if allowed else CanonicalEffect.DENY,
            identity=identity,
            role=role.name,
            resource=resource,
            reason=f"Matched rule with effect='{matched_effect}'",
            reason_code=CanonicalReasonCode.ALLOWED if allowed else CanonicalReasonCode.DENIED_BY_RULE,
        )

    def filter_catalogs(self, identity: str, catalogs):
        return [c for c in catalogs if self._is_allowed(identity, c.adapter, c.catalog)]

    def filter_schemas(self, identity: str, adapter: str, schemas):
        return [
            s for s in schemas if self._is_allowed(identity, adapter, s.catalog, s.schema_name)
        ]

    def filter_tables(self, identity: str, adapter: str, catalog: str, schema: str, tables):
        return [
            t
            for t in tables
            if self._is_allowed(identity, adapter, catalog, schema, t.table_ref.table)
        ]
