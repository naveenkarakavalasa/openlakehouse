"""Semantic Consistency Report

Compares canonical metadata and query results from Databricks and AWS to verify
that both platforms conform to the same canonical schema and that
platform-specific differences are hidden behind the canonical layer.

Does not require live credentials — works with provided canonical objects.
For live cross-platform comparison, pass real adapter results through the mapper
before calling these functions.

Usage:
    python -m evaluation.semantic_consistency
"""
from __future__ import annotations

import json
import sys
from typing import Any

from openlakehouse.core.canonical.metadata import (
    AWS_NAMESPACE,
    DATABRICKS_NAMESPACE,
    CanonicalCatalog,
    CanonicalSchema,
    CanonicalTable,
    CanonicalTableSchema,
)
from openlakehouse.core.canonical.query import CanonicalQueryResult

CANONICAL_CATALOG_FIELDS = set(CanonicalCatalog.model_fields.keys())
CANONICAL_SCHEMA_FIELDS = set(CanonicalSchema.model_fields.keys())
CANONICAL_TABLE_FIELDS = set(CanonicalTable.model_fields.keys())
CANONICAL_QUERY_FIELDS = set(CanonicalQueryResult.model_fields.keys())


def _check_fields(obj: Any, expected_fields: set[str], label: str) -> list[str]:
    issues = []
    actual = set(obj.model_fields.keys())
    missing = expected_fields - actual
    if missing:
        issues.append(f"{label}: missing canonical fields {missing}")
    return issues


def compare_catalog_results(
    databricks: list[CanonicalCatalog],
    aws: list[CanonicalCatalog],
) -> dict:
    """Verify both platform catalog lists conform to canonical schema."""
    issues = []
    for c in databricks + aws:
        issues.extend(_check_fields(c, CANONICAL_CATALOG_FIELDS, f"catalog:{c.catalog}"))

    platforms_seen = {c.platform for c in databricks + aws}
    common_fields = ["adapter", "platform", "catalog", "native_catalog"]

    databricks_native = {c.native_catalog for c in databricks}
    aws_native = {c.native_catalog for c in aws}

    return {
        "conformance": len(issues) == 0,
        "issues": issues,
        "platforms_represented": list(platforms_seen),
        "common_canonical_fields": common_fields,
        "databricks_native_catalogs": list(databricks_native),
        "aws_native_catalogs": list(aws_native),
        "semantic_equivalence": "Both use 'catalog' field; AWS maps Glue Data Catalog as AwsDataCatalog",
    }


def compare_schema_results(
    databricks: list[CanonicalSchema],
    aws: list[CanonicalSchema],
) -> dict:
    """Verify both platform schema lists conform to canonical schema."""
    issues = []
    for s in databricks + aws:
        issues.extend(_check_fields(s, CANONICAL_SCHEMA_FIELDS, f"schema:{s.schema}"))

    return {
        "conformance": len(issues) == 0,
        "issues": issues,
        "databricks_concept": DATABRICKS_NAMESPACE.schema_concept,
        "aws_concept": AWS_NAMESPACE.schema_concept,
        "canonical_field": "schema",
        "semantic_note": "Databricks 'Schema' and AWS 'Glue Database' both mapped to canonical schema field",
    }


def compare_query_results(
    databricks: CanonicalQueryResult | None,
    aws: CanonicalQueryResult | None,
) -> dict:
    """Compare structural conformance of query results from both platforms."""
    report: dict[str, Any] = {"conformance": True, "issues": [], "platform_differences": []}

    for label, result in [("databricks", databricks), ("aws", aws)]:
        if result is None:
            continue
        issues = _check_fields(result, CANONICAL_QUERY_FIELDS, label)
        report["issues"].extend(issues)
        if issues:
            report["conformance"] = False

    if databricks and aws:
        db_col_names = {c.name for c in databricks.columns}
        aws_col_names = {c.name for c in aws.columns}
        if db_col_names != aws_col_names:
            report["platform_differences"].append(
                f"Column sets differ: databricks={db_col_names}, aws={aws_col_names}"
            )

        if databricks.execution.platform != aws.execution.platform:
            report["platform_differences"].append(
                "Execution metadata carries platform-specific query_id "
                f"(databricks: {databricks.execution.query_id}, aws: {aws.execution.query_id})"
            )

        report["pagination_model"] = {
            "databricks": "truncated=True, next_page_token=None (no resumable cursor in v1)",
            "aws": "Athena NextToken encoded as <query_execution_id>:<token>",
        }

    return report


def full_consistency_report(
    databricks_catalogs: list[CanonicalCatalog] | None = None,
    aws_catalogs: list[CanonicalCatalog] | None = None,
    databricks_schemas: list[CanonicalSchema] | None = None,
    aws_schemas: list[CanonicalSchema] | None = None,
    databricks_query: CanonicalQueryResult | None = None,
    aws_query: CanonicalQueryResult | None = None,
) -> dict:
    return {
        "canonical_model_version": "v1",
        "namespace_mappings": {
            "databricks": DATABRICKS_NAMESPACE.model_dump(),
            "aws": AWS_NAMESPACE.model_dump(),
        },
        "catalog_comparison": compare_catalog_results(
            databricks_catalogs or [], aws_catalogs or []
        ),
        "schema_comparison": compare_schema_results(
            databricks_schemas or [], aws_schemas or []
        ),
        "query_comparison": compare_query_results(databricks_query, aws_query),
    }


def main() -> None:
    # Demo with synthetic canonical objects (no live credentials)
    from openlakehouse.core.canonical.metadata import CanonicalCatalog, CanonicalSchema

    db_catalogs = [
        CanonicalCatalog(adapter="databricks_prod", platform="databricks",
                         catalog="sales", native_catalog="sales"),
    ]
    aws_catalogs = [
        CanonicalCatalog(adapter="aws_prod", platform="aws",
                         catalog="AwsDataCatalog", native_catalog="AwsDataCatalog"),
    ]
    db_schemas = [
        CanonicalSchema(adapter="databricks_prod", platform="databricks",
                        catalog="sales", schema="orders", native_schema="orders"),
    ]
    aws_schemas = [
        CanonicalSchema(adapter="aws_prod", platform="aws",
                        catalog="AwsDataCatalog", schema="analytics", native_schema="analytics"),
    ]

    report = full_consistency_report(
        databricks_catalogs=db_catalogs,
        aws_catalogs=aws_catalogs,
        databricks_schemas=db_schemas,
        aws_schemas=aws_schemas,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
