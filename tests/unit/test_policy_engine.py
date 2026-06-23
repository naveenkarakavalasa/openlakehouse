import pytest

from openlakehouse.core.errors import PermissionDeniedError
from openlakehouse.core.models import CatalogRef, SchemaRef, TableRef, TableSummary
from openlakehouse.policy.engine import PolicyEngine
from openlakehouse.policy.models import PolicyDocument, PolicyRule, Role


def _doc(**overrides) -> PolicyDocument:
    base = dict(
        identities={"analyst-bot": "analyst"},
        default_role=None,
        roles={
            "analyst": Role(
                name="analyst",
                can_execute_queries=True,
                rules=[
                    PolicyRule(effect="allow", adapter="db1", catalog="sales", schema_name="*", table="*"),
                    PolicyRule(effect="deny", adapter="db1", catalog="sales", schema_name="pii", table="*"),
                ],
            )
        },
    )
    base.update(overrides)
    return PolicyDocument(**base)


def test_unknown_identity_with_no_default_role_is_denied():
    engine = PolicyEngine(_doc())
    with pytest.raises(PermissionDeniedError):
        engine.authorize("nobody", adapter="db1", catalog="sales")


def test_allow_then_deny_last_match_wins():
    engine = PolicyEngine(_doc())
    # allowed: sales.public.orders
    engine.authorize("analyst-bot", adapter="db1", catalog="sales", schema="public", table="orders")
    # denied: sales.pii.* even though a broader allow matches earlier
    with pytest.raises(PermissionDeniedError):
        engine.authorize("analyst-bot", adapter="db1", catalog="sales", schema="pii", table="ssn")


def test_no_matching_rule_is_default_deny():
    engine = PolicyEngine(_doc())
    with pytest.raises(PermissionDeniedError):
        engine.authorize("analyst-bot", adapter="db1", catalog="marketing", schema="public", table="leads")


def test_can_execute_queries_false_blocks_run_query_but_not_listing():
    doc = _doc()
    doc.roles["analyst"].can_execute_queries = False
    engine = PolicyEngine(doc)

    with pytest.raises(PermissionDeniedError):
        engine.authorize("analyst-bot", adapter="db1", catalog="sales", schema="public", for_query=True)

    # non-query access (e.g. listing) is unaffected by can_execute_queries
    engine.authorize("analyst-bot", adapter="db1", catalog="sales", schema="public")


def test_filter_tables_drops_only_denied_table():
    engine = PolicyEngine(_doc())
    tables = [
        TableSummary(table_ref=TableRef(adapter="db1", catalog="sales", schema="pii", table="ssn")),
        TableSummary(table_ref=TableRef(adapter="db1", catalog="sales", schema="pii", table="orders")),
    ]
    # both tables are under schema "pii" which is denied entirely
    visible = engine.filter_tables("analyst-bot", "db1", "sales", "pii", tables)
    assert visible == []


def test_filter_catalogs_and_schemas():
    engine = PolicyEngine(_doc())
    catalogs = [CatalogRef(adapter="db1", catalog="sales"), CatalogRef(adapter="db1", catalog="marketing")]
    assert engine.filter_catalogs("analyst-bot", catalogs) == [catalogs[0]]

    schemas = [
        SchemaRef(adapter="db1", catalog="sales", schema="public"),
        SchemaRef(adapter="db1", catalog="sales", schema="pii"),
    ]
    visible = engine.filter_schemas("analyst-bot", "db1", schemas)
    assert [s.schema_name for s in visible] == ["public"]


def test_default_role_applies_to_unknown_identity():
    doc = _doc(default_role="analyst")
    engine = PolicyEngine(doc)
    engine.authorize("some-other-bot", adapter="db1", catalog="sales", schema="public")


def test_admin_wildcard_role_allows_everything():
    doc = _doc(
        roles={
            "admin": Role(
                name="admin",
                rules=[PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")],
            )
        },
        identities={"admin-bot": "admin"},
    )
    engine = PolicyEngine(doc)
    engine.authorize("admin-bot", adapter="anything", catalog="anything", schema="anything", table="anything")
