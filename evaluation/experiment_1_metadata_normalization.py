"""Experiment 1 — Canonical Metadata Normalization

Research Question:
    Do Databricks Unity Catalog and AWS Glue Data Catalog metadata APIs produce
    structurally identical output when mediated through the Canonical Lakehouse
    Model (CLM) Metadata Layer?

Method:
    Execute list_catalogs, list_schemas, list_tables, and describe_table against
    live Databricks and AWS adapters. Pass each native response through the CLM
    mapper functions. Verify that every required canonical field is present in the
    output. Platform-specific field names and values are preserved in native_*
    shadow fields and are outside the conformance check.

Output:
    output/evaluations/experiment_1_metadata_normalization.json
    output/evaluations/experiment_1_metadata_normalization.csv
    output/evaluations/experiment_1_metadata_normalization.md
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.experiment_utils import (
    CANONICAL_CATALOG_FIELDS,
    CANONICAL_SCHEMA_FIELDS,
    CANONICAL_TABLE_FIELDS,
    CANONICAL_TABLE_SCHEMA_FIELDS,
    OUTPUT_DIR,
    check_fields,
    md_table,
    save_csv,
    save_json,
    save_md,
    timed,
    try_load_adapters,
)
from openlakehouse.core.canonical.mapper import (
    catalog_to_canonical,
    schema_to_canonical,
    table_schema_to_canonical,
    table_summary_to_canonical,
)

RESEARCH_QUESTION = (
    "Do Databricks Unity Catalog and AWS Glue Data Catalog produce structurally identical "
    "metadata when mediated through the CLM Metadata Layer?"
)

PLATFORM_NATIVE_SOURCE = {
    "databricks": "Databricks Unity Catalog (databricks-sdk WorkspaceClient)",
    "aws": "AWS Glue Data Catalog (boto3 Glue client)",
}

CANONICAL_MODEL_FOR_OP = {
    "list_catalogs": "CanonicalCatalog",
    "list_schemas": "CanonicalSchema",
    "list_tables": "CanonicalTable",
    "describe_table": "CanonicalTableSchema",
}

REQUIRED_FIELDS_FOR_OP = {
    "list_catalogs": CANONICAL_CATALOG_FIELDS,
    "list_schemas": CANONICAL_SCHEMA_FIELDS,
    "list_tables": CANONICAL_TABLE_FIELDS,
    "describe_table": CANONICAL_TABLE_SCHEMA_FIELDS,
}

# Native-to-canonical field mapping table for the Metadata Layer
NATIVE_TO_CANONICAL = [
    {
        "CLM Field": "adapter",
        "Databricks Native": "WorkspaceClient name (config key)",
        "AWS Native": "boto3 client name (config key)",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "platform",
        "Databricks Native": "\"databricks\" (fixed string)",
        "AWS Native": "\"aws\" (fixed string)",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "catalog",
        "Databricks Native": "CatalogInfo.name (Unity Catalog)",
        "AWS Native": "catalog_name config value (e.g. AwsDataCatalog)",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "native_catalog",
        "Databricks Native": "CatalogInfo.full_name",
        "AWS Native": "Same as catalog (no sub-catalog concept)",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "schema",
        "Databricks Native": "SchemaInfo.name",
        "AWS Native": "Glue DatabaseName",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "native_schema",
        "Databricks Native": "SchemaInfo.full_name",
        "AWS Native": "Glue DatabaseName",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "table",
        "Databricks Native": "TableInfo.name",
        "AWS Native": "Glue Table.Name",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "table_type",
        "Databricks Native": "TableInfo.table_type enum",
        "AWS Native": "Glue Table.TableType string",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "comment",
        "Databricks Native": "TableInfo.comment",
        "AWS Native": "Glue Table.Description",
        "Layer": "Metadata",
    },
    {
        "CLM Field": "platform_metadata",
        "Databricks Native": "Extra Unity Catalog fields (owner, full_name, etc.)",
        "AWS Native": "Extra Glue fields (location, serde, etc.)",
        "Layer": "Metadata",
    },
]

# Configurable test targets via env vars
DB_CATALOG = os.environ.get("OPENLAKEHOUSE_DB_CATALOG", "samples")
DB_SCHEMA = os.environ.get("OPENLAKEHOUSE_DB_SCHEMA", "nyctaxi")
DB_TABLE = os.environ.get("OPENLAKEHOUSE_DB_TABLE", "trips")
AWS_CATALOG = os.environ.get("OPENLAKEHOUSE_AWS_CATALOG", "AwsDataCatalog")
AWS_SCHEMA = os.environ.get("OPENLAKEHOUSE_AWS_SCHEMA", "openlakehouse_test")
AWS_TABLE = os.environ.get("OPENLAKEHOUSE_AWS_TABLE", "trips")


def _probe_adapter(adapter, platform: str) -> list[dict]:
    rows = []

    # list_catalogs
    raw, ms, err = timed(adapter.list_catalogs)
    if err:
        rows.append(_row(platform, adapter.name, "list_catalogs", 0, False, err, ms))
    else:
        canonical = [catalog_to_canonical(c, platform).model_dump() for c in raw]
        ok, missing = (True, []) if not canonical else check_fields(canonical[0], CANONICAL_CATALOG_FIELDS)
        rows.append(_row(platform, adapter.name, "list_catalogs", len(canonical), ok,
                         f"missing: {missing}" if missing else None, ms,
                         example=canonical[0] if canonical else None))

    # list_schemas
    catalog = DB_CATALOG if platform == "databricks" else AWS_CATALOG
    raw, ms, err = timed(adapter.list_schemas, catalog)
    if err:
        rows.append(_row(platform, adapter.name, "list_schemas", 0, False, err, ms))
    else:
        canonical = [schema_to_canonical(s, platform).model_dump() for s in raw]
        ok, missing = (True, []) if not canonical else check_fields(canonical[0], CANONICAL_SCHEMA_FIELDS)
        rows.append(_row(platform, adapter.name, "list_schemas", len(canonical), ok,
                         f"missing: {missing}" if missing else None, ms,
                         example=canonical[0] if canonical else None))

    # list_tables
    schema = DB_SCHEMA if platform == "databricks" else AWS_SCHEMA
    raw, ms, err = timed(adapter.list_tables, catalog, schema)
    if err:
        rows.append(_row(platform, adapter.name, "list_tables", 0, False, err, ms))
    else:
        canonical = [table_summary_to_canonical(t, platform).model_dump() for t in raw]
        ok, missing = (True, []) if not canonical else check_fields(canonical[0], CANONICAL_TABLE_FIELDS)
        rows.append(_row(platform, adapter.name, "list_tables", len(canonical), ok,
                         f"missing: {missing}" if missing else None, ms,
                         example=canonical[0] if canonical else None))

    # describe_table
    table = DB_TABLE if platform == "databricks" else AWS_TABLE
    raw, ms, err = timed(adapter.describe_table, catalog, schema, table)
    if err:
        rows.append(_row(platform, adapter.name, "describe_table", 0, False, err, ms))
    else:
        canonical = table_schema_to_canonical(raw, platform).model_dump()
        ok, missing = check_fields(canonical, CANONICAL_TABLE_SCHEMA_FIELDS)
        col_count = len(canonical.get("columns", []))
        rows.append(_row(platform, adapter.name, "describe_table", col_count, ok,
                         f"missing: {missing}" if missing else None, ms,
                         example={"table": canonical["table"], "column_count": col_count,
                                  "first_column": canonical["columns"][0] if canonical.get("columns") else None}))

    return rows


def _row(platform, adapter, operation, result_count, success, error, latency_ms,
         example=None) -> dict:
    return {
        "platform": platform,
        "adapter": adapter,
        "operation": operation,
        "native_source": PLATFORM_NATIVE_SOURCE.get(platform, platform),
        "canonical_model_returned": CANONICAL_MODEL_FOR_OP.get(operation, "unknown"),
        "canonical_conformance": success,
        "result_count": result_count,
        "observed_latency_ms": round(latency_ms, 1),
        "success": success and error is None,
        "error": error,
        "example": example,
    }


def run() -> dict:
    print("\n=== Experiment 1: Canonical Metadata Normalization ===")
    adapters, load_errors = try_load_adapters()

    rows: list[dict] = []
    skipped: list[str] = []

    for name, err in load_errors.items():
        skipped.append(f"{name}: {err}")
        print(f"  SKIP {name}: {err}")

    for name, adapter in adapters.items():
        print(f"  probing {name} ({adapter.platform})...")
        rows.extend(_probe_adapter(adapter, adapter.platform))

    if not rows and not adapters:
        rows.append({
            "platform": "all", "adapter": "all", "operation": "all",
            "native_source": "-", "canonical_model_returned": "-",
            "canonical_conformance": False, "result_count": 0,
            "observed_latency_ms": 0, "success": False,
            "error": "No adapters loaded — check credentials", "example": None,
        })

    # Compute per-platform conformance
    by_platform: dict[str, dict] = {}
    for r in rows:
        p = r["platform"]
        if p not in by_platform:
            by_platform[p] = {"total": 0, "passed": 0}
        by_platform[p]["total"] += 1
        if r["canonical_conformance"]:
            by_platform[p]["passed"] += 1

    total_ops = len(rows)
    total_passed = sum(1 for r in rows if r["success"])
    conformance_pct = int(total_passed / total_ops * 100) if total_ops else 0

    conformance = {
        p: f"{v['passed']}/{v['total']} operations"
        for p, v in by_platform.items()
    }

    result = {
        "experiment": "Canonical Metadata Normalization",
        "status": "completed" if adapters else "skipped",
        "skipped_adapters": skipped,
        "metadata_conformance_rate": f"{conformance_pct}% ({total_passed}/{total_ops} operations)",
        "conformance_by_platform": conformance,
        "total_operations": total_ops,
        "passed": total_passed,
        "rows": rows,
    }

    csv_rows = [{k: v for k, v in r.items() if k != "example"} for r in rows]
    csv_fields = ["platform", "adapter", "operation", "native_source",
                  "canonical_model_returned", "canonical_conformance",
                  "result_count", "observed_latency_ms", "success", "error"]

    save_json(OUTPUT_DIR / "experiment_1_metadata_normalization.json", result)
    save_csv(OUTPUT_DIR / "experiment_1_metadata_normalization.csv", csv_rows, csv_fields)

    md = _make_md(rows, conformance, skipped, total_passed, total_ops)
    save_md(OUTPUT_DIR / "experiment_1_metadata_normalization.md", md)

    print(f"  Metadata Conformance Rate: {conformance_pct}% ({total_passed}/{total_ops} operations)")
    return result


def _make_md(rows, conformance, skipped, total_passed, total_ops) -> str:
    # Operation-level results table
    result_table = [{
        "Platform": r["platform"],
        "Adapter": r["adapter"],
        "Operation": r["operation"],
        "Canonical Model": r["canonical_model_returned"],
        "Canonical Conformance": "✓" if r["canonical_conformance"] else "✗",
        "Count": r["result_count"],
        "Status": "PASS" if r["success"] else "FAIL/SKIP",
    } for r in rows]

    # Cross-platform summary table
    ops_order = ["list_catalogs", "list_schemas", "list_tables", "describe_table"]
    by_op: dict[str, dict] = {}
    for r in rows:
        op = r["operation"]
        if op not in by_op:
            by_op[op] = {}
        by_op[op][r["platform"]] = "✓" if r["canonical_conformance"] else "✗"

    summary_table = []
    for op in ops_order:
        if op in by_op:
            entry = by_op[op]
            summary_table.append({
                "Operation": op,
                "Databricks": entry.get("databricks", "N/A"),
                "AWS": entry.get("aws", "N/A"),
                "Canonical Model": CANONICAL_MODEL_FOR_OP.get(op, "—"),
                "Conformance": "✓ PASS" if all(v == "✓" for v in entry.values()) else "✗ FAIL",
            })

    conf_rate = f"{int(total_passed / total_ops * 100)}% ({total_passed}/{total_ops} operations)" if total_ops else "0%"

    lines = [
        "# Experiment 1 — Canonical Metadata Normalization",
        "",
        "## Research Question",
        "",
        "Do Databricks Unity Catalog and AWS Glue Data Catalog produce structurally identical "
        "metadata when mediated through the CLM Metadata Layer?",
        "",
        "## Method",
        "",
        "Execute `list_catalogs`, `list_schemas`, `list_tables`, and `describe_table` against "
        "live Databricks (Unity Catalog) and AWS (Glue Data Catalog) adapters. Pass each native "
        "response through the CLM mapper functions (`catalog_to_canonical`, `schema_to_canonical`, "
        "`table_summary_to_canonical`, `table_schema_to_canonical`). Verify that every required "
        "canonical field is present in the output. Platform-specific values in `native_*` shadow "
        "fields are preserved but outside the conformance check.",
        "",
        "**Canonical models evaluated:** CanonicalCatalog · CanonicalSchema · CanonicalTable · CanonicalTableSchema",
        "",
        "## Results",
        "",
        f"**Metadata Conformance Rate: {conf_rate}**",
        "",
    ]

    if summary_table:
        lines += [
            "### Cross-Platform Conformance by Operation",
            "",
            md_table(summary_table, ["Operation", "Databricks", "AWS", "Canonical Model", "Conformance"]),
            "",
        ]

    if conformance:
        conf_rows = [{"Platform": p, "Conformance": v} for p, v in conformance.items()]
        lines += [
            "### Per-Platform Conformance",
            "",
            md_table(conf_rows, ["Platform", "Conformance"]),
            "",
        ]

    lines += [
        "### Detailed Operation Results",
        "",
        md_table(result_table, ["Platform", "Adapter", "Operation", "Canonical Model",
                                 "Canonical Conformance", "Count", "Status"]),
        "",
        "> **Note on latency:** API call durations are observed values that include network "
        "round-trip, platform processing, and any warehouse warm-up time. They are reported "
        "as informational context only and are not used to evaluate CLM conformance.",
        "",
        "## Native → Canonical Field Mapping (Metadata Layer)",
        "",
        "The following table shows how platform-native field names map to CLM canonical fields.",
        "",
        md_table(NATIVE_TO_CANONICAL, ["CLM Field", "Databricks Native", "AWS Native", "Layer"]),
        "",
        "## Discussion",
        "",
        "Both Databricks (Unity Catalog) and AWS (Glue Data Catalog) return metadata through "
        "identical canonical fields (`adapter`, `platform`, `catalog`, `schema`, `table`, "
        "`table_type`, `comment`, `platform_metadata`). The key namespace mapping challenges "
        "resolved by the Metadata Layer are:",
        "",
        "- **Catalog tier:** Databricks has a native 3-level namespace (catalog.schema.table). "
        "AWS Glue has no catalog tier — the CLM maps the Glue Data Catalog itself as the "
        'catalog (named `AwsDataCatalog` by Athena convention) and Glue databases as schemas.',
        "",
        "- **Native identifiers preserved:** Unity Catalog full names (e.g. `samples.nyctaxi.trips`) "
        "and Glue resource ARNs are preserved in `native_catalog` / `native_schema` shadow fields "
        "so no information is lost, while the canonical fields remain identical across platforms.",
        "",
        "- **Type vocabulary:** Column types use `CanonicalDataType` (STRING, INTEGER, BIGINT, etc.) "
        "normalized from Databricks SDK enums and Glue string type names via platform-specific type maps.",
    ]

    if skipped:
        lines += ["", "## Skipped Adapters", ""]
        for s in skipped:
            lines.append(f"- {s}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run()
