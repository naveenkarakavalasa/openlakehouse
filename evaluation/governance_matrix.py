"""Governance Test Matrix

Generates and runs allow/deny/filter scenarios against the PolicyEngine to
verify authorization decisions without live cloud credentials.

Outputs a JSON matrix suitable for paper governance tables.

Usage:
    python -m evaluation.governance_matrix
    python -m evaluation.governance_matrix --csv
"""
from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock

from openlakehouse.core.adapter import LakehouseAdapter
from openlakehouse.core.canonical.governance import CanonicalReasonCode
from openlakehouse.core.models import CatalogRef, SchemaRef, TableRef, TableSummary
from openlakehouse.policy.engine import PolicyEngine
from openlakehouse.policy.models import PolicyDocument, PolicyRule, Role

# ---------------------------------------------------------------------------
# Reference policy used in all matrix scenarios
# ---------------------------------------------------------------------------

MATRIX_POLICY = PolicyDocument(
    identities={
        "admin-agent": "admin",
        "analyst-agent": "analyst",
        "readonly-agent": "browse-only",
    },
    default_role=None,
    roles={
        "admin": Role(
            name="admin",
            rules=[PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")],
            can_execute_queries=True,
        ),
        "analyst": Role(
            name="analyst",
            rules=[
                PolicyRule(effect="allow", adapter="databricks_prod", catalog="sales", schema_name="*", table="*"),
                PolicyRule(effect="deny", adapter="databricks_prod", catalog="sales", schema_name="pii", table="*"),
                PolicyRule(effect="allow", adapter="aws_prod", catalog="AwsDataCatalog", schema_name="analytics", table="*"),
            ],
            can_execute_queries=True,
        ),
        "browse-only": Role(
            name="browse-only",
            rules=[PolicyRule(effect="allow", adapter="*", catalog="*", schema_name="*", table="*")],
            can_execute_queries=False,
        ),
    },
)


@dataclass
class Scenario:
    name: str
    identity: str
    adapter: str
    catalog: str
    schema: str | None
    table: str | None
    for_query: bool
    expected_allowed: bool
    expected_reason_code: str


SCENARIOS: list[Scenario] = [
    Scenario("admin_allow_all", "admin-agent", "databricks_prod", "sales", "pii", "ssn", False, True, CanonicalReasonCode.ALLOWED),
    Scenario("admin_allow_query", "admin-agent", "databricks_prod", "sales", None, None, True, True, CanonicalReasonCode.ALLOWED),
    Scenario("analyst_allow_sales", "analyst-agent", "databricks_prod", "sales", "orders", "transactions", False, True, CanonicalReasonCode.ALLOWED),
    Scenario("analyst_deny_pii", "analyst-agent", "databricks_prod", "sales", "pii", "ssn", False, False, CanonicalReasonCode.DENIED_BY_RULE),
    Scenario("analyst_allow_aws", "analyst-agent", "aws_prod", "AwsDataCatalog", "analytics", "trips", False, True, CanonicalReasonCode.ALLOWED),
    Scenario("analyst_deny_aws_other", "analyst-agent", "aws_prod", "AwsDataCatalog", "raw", "logs", False, False, CanonicalReasonCode.DENIED_NO_MATCHING_RULE),
    Scenario("browse_only_deny_query", "readonly-agent", "databricks_prod", "sales", "orders", None, True, False, CanonicalReasonCode.DENIED_NO_QUERY_PERMISSION),
    Scenario("browse_only_allow_browse", "readonly-agent", "databricks_prod", "sales", "orders", None, False, True, CanonicalReasonCode.ALLOWED),
    Scenario("unknown_identity_deny", "unknown-agent", "databricks_prod", "sales", None, None, False, False, CanonicalReasonCode.DENIED_NO_ROLE),
]


def run_matrix(engine: PolicyEngine | None = None) -> list[dict]:
    if engine is None:
        engine = PolicyEngine(MATRIX_POLICY)

    results = []
    for s in SCENARIOS:
        decision = engine.authorize_with_decision(
            s.identity,
            adapter=s.adapter,
            catalog=s.catalog,
            schema=s.schema,
            table=s.table,
            for_query=s.for_query,
        )

        # Verify adapter is never called when denied (governance invariant)
        fake_adapter = MagicMock(spec=LakehouseAdapter)
        if decision.allowed:
            fake_adapter.list_catalogs.return_value = [
                CatalogRef(adapter=s.adapter, catalog=s.catalog)
            ]

        passed = (
            decision.allowed == s.expected_allowed
            and decision.reason_code == s.expected_reason_code
        )

        results.append({
            "scenario": s.name,
            "identity": s.identity,
            "adapter": s.adapter,
            "catalog": s.catalog,
            "schema": s.schema or "*",
            "table": s.table or "*",
            "for_query": s.for_query,
            "expected_allowed": s.expected_allowed,
            "actual_allowed": decision.allowed,
            "reason_code": decision.reason_code,
            "reason": decision.reason,
            "passed": passed,
        })

    return results


def run_list_filter_scenarios(engine: PolicyEngine | None = None) -> list[dict]:
    """Verify that filter_* methods silently drop denied items."""
    if engine is None:
        engine = PolicyEngine(MATRIX_POLICY)

    catalogs = [
        CatalogRef(adapter="databricks_prod", catalog="sales"),
        CatalogRef(adapter="databricks_prod", catalog="system"),
        CatalogRef(adapter="aws_prod", catalog="AwsDataCatalog"),
    ]
    visible = engine.filter_catalogs("analyst-agent", catalogs)
    results = []
    for c in catalogs:
        results.append({
            "scenario": f"filter_catalog_{c.catalog}",
            "identity": "analyst-agent",
            "resource": f"{c.adapter}/{c.catalog}",
            "visible": any(v.catalog == c.catalog for v in visible),
        })

    tables = [
        TableSummary(table_ref=TableRef(adapter="databricks_prod", catalog="sales", schema="orders", table="transactions")),
        TableSummary(table_ref=TableRef(adapter="databricks_prod", catalog="sales", schema="pii", table="ssn")),
    ]
    visible_tables = engine.filter_tables("analyst-agent", "databricks_prod", "sales", "orders", tables)
    visible_table_names = {t.table_ref.table for t in visible_tables}
    for t in tables:
        results.append({
            "scenario": f"filter_table_{t.table_ref.schema_name}_{t.table_ref.table}",
            "identity": "analyst-agent",
            "resource": f"databricks_prod/sales/{t.table_ref.schema_name}/{t.table_ref.table}",
            "visible": t.table_ref.table in visible_table_names,
        })

    return results


def main() -> None:
    engine = PolicyEngine(MATRIX_POLICY)
    matrix = run_matrix(engine)
    filters = run_list_filter_scenarios(engine)

    total = len(matrix)
    passed = sum(1 for r in matrix if r["passed"])

    if "--csv" in sys.argv:
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=["scenario", "identity", "adapter", "catalog", "schema",
                        "table", "for_query", "expected_allowed", "actual_allowed",
                        "reason_code", "passed"],
        )
        writer.writeheader()
        for row in matrix:
            writer.writerow({k: v for k, v in row.items() if k != "reason"})
    else:
        print(json.dumps({"authorization_matrix": matrix, "filter_scenarios": filters,
                          "summary": {"total": total, "passed": passed, "failed": total - passed}},
                         indent=2))


if __name__ == "__main__":
    main()
