"""Unit tests for canonical governance models and authorization decisions."""
import pytest
from openlakehouse.core.canonical.governance import (
    CanonicalAuthorizationDecision,
    CanonicalEffect,
    CanonicalPermission,
    CanonicalPolicy,
    CanonicalPolicyRule,
    CanonicalReasonCode,
    CanonicalResourceScope,
    CanonicalRole,
)
from openlakehouse.policy.engine import PolicyEngine
from openlakehouse.policy.models import PolicyDocument, PolicyRule, Role


def _engine_with_roles(**roles_kwargs) -> PolicyEngine:
    roles = {}
    for name, rules in roles_kwargs.items():
        roles[name] = Role(name=name, rules=rules)
    doc = PolicyDocument(
        identities={"user": list(roles_kwargs.keys())[0]},
        roles=roles,
    )
    return PolicyEngine(doc)


def test_resource_scope_str():
    scope = CanonicalResourceScope(adapter="db", catalog="sales", schema="pii", table="ssn")
    assert str(scope) == "db/sales/pii/ssn"


def test_canonical_permission_values():
    assert CanonicalPermission.BROWSE == "browse"
    assert CanonicalPermission.QUERY == "query"


def test_authorize_with_decision_allowed():
    doc = PolicyDocument(
        identities={"agent": "admin"},
        roles={"admin": Role(name="admin", rules=[
            PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")
        ])},
    )
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision("agent", adapter="db", catalog="sales")
    assert decision.allowed is True
    assert decision.effect == CanonicalEffect.ALLOW
    assert decision.reason_code == CanonicalReasonCode.ALLOWED
    assert decision.role == "admin"


def test_authorize_with_decision_denied_by_rule():
    doc = PolicyDocument(
        identities={"agent": "analyst"},
        roles={"analyst": Role(name="analyst", rules=[
            PolicyRule(effect="allow", adapter="db", catalog="sales", schema_name="*", table="*"),
            PolicyRule(effect="deny", adapter="db", catalog="sales", schema_name="pii", table="*"),
        ])},
    )
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision("agent", adapter="db", catalog="sales", schema="pii")
    assert decision.allowed is False
    assert decision.effect == CanonicalEffect.DENY
    assert decision.reason_code == CanonicalReasonCode.DENIED_BY_RULE


def test_authorize_with_decision_no_matching_rule():
    doc = PolicyDocument(
        identities={"agent": "analyst"},
        roles={"analyst": Role(name="analyst", rules=[
            PolicyRule(effect="allow", adapter="db", catalog="sales", schema_name="*", table="*"),
        ])},
    )
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision("agent", adapter="db", catalog="finance")
    assert decision.allowed is False
    assert decision.reason_code == CanonicalReasonCode.DENIED_NO_MATCHING_RULE


def test_authorize_with_decision_no_role():
    doc = PolicyDocument(identities={}, roles={}, default_role=None)
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision("unknown", adapter="db", catalog="sales")
    assert decision.allowed is False
    assert decision.role is None
    assert decision.reason_code == CanonicalReasonCode.DENIED_NO_ROLE


def test_authorize_with_decision_no_query_permission():
    doc = PolicyDocument(
        identities={"agent": "browse-only"},
        roles={"browse-only": Role(
            name="browse-only",
            rules=[PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")],
            can_execute_queries=False,
        )},
    )
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision("agent", adapter="db", catalog="sales", for_query=True)
    assert decision.allowed is False
    assert decision.reason_code == CanonicalReasonCode.DENIED_NO_QUERY_PERMISSION


def test_authorize_with_decision_resource_scope_populated():
    doc = PolicyDocument(
        identities={"agent": "admin"},
        roles={"admin": Role(name="admin", rules=[
            PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")
        ])},
    )
    engine = PolicyEngine(doc)
    decision = engine.authorize_with_decision(
        "agent", adapter="db", catalog="sales", schema="orders", table="transactions"
    )
    assert decision.resource.adapter == "db"
    assert decision.resource.catalog == "sales"
    assert decision.resource.schema_name == "orders"
    assert decision.resource.table == "transactions"


def test_authorize_still_raises_permission_denied():
    """authorize() must still raise for backward compatibility."""
    from openlakehouse.core.errors import PermissionDeniedError
    doc = PolicyDocument(identities={}, roles={}, default_role=None)
    engine = PolicyEngine(doc)
    with pytest.raises(PermissionDeniedError):
        engine.authorize("unknown", adapter="db", catalog="sales")


def test_canonical_policy_models():
    policy = CanonicalPolicy(
        identities={"agent": "admin"},
        roles={
            "admin": CanonicalRole(
                name="admin",
                rules=[CanonicalPolicyRule(
                    effect=CanonicalEffect.ALLOW,
                    scope=CanonicalResourceScope(),
                )],
                permissions={CanonicalPermission.BROWSE, CanonicalPermission.QUERY},
            )
        },
    )
    assert "admin" in policy.roles
    assert CanonicalPermission.QUERY in policy.roles["admin"].permissions
