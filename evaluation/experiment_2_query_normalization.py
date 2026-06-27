"""Experiment 2 — Canonical Query Normalization

Verifies that Databricks SQL Warehouse and AWS Athena return query results
through the same CanonicalQueryResult shape, including columns, rows,
pagination, and execution metadata.

Environment variables (optional):
    OPENLAKEHOUSE_DATABRICKS_TEST_SQL   — SQL to run on Databricks (default: SELECT 1 AS n)
    OPENLAKEHOUSE_AWS_TEST_SQL          — SQL to run on Athena (default: SELECT 1 AS n)
    OPENLAKEHOUSE_DB_CATALOG            — Databricks catalog context
    OPENLAKEHOUSE_DB_SCHEMA             — Databricks schema context
    OPENLAKEHOUSE_AWS_CATALOG           — AWS catalog context
    OPENLAKEHOUSE_AWS_SCHEMA            — AWS schema context

Output:
    output/evaluations/experiment_2_query_normalization.json
    output/evaluations/experiment_2_query_normalization.csv
    output/evaluations/experiment_2_query_normalization.md
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.experiment_utils import (
    CANONICAL_EXECUTION_FIELDS,
    CANONICAL_PAGINATION_FIELDS,
    CANONICAL_QUERY_FIELDS,
    OUTPUT_DIR,
    check_fields,
    md_table,
    save_csv,
    save_json,
    save_md,
    timed,
    try_load_adapters,
)
from openlakehouse.core.canonical.mapper import query_result_to_canonical

DB_SQL = os.environ.get("OPENLAKEHOUSE_DATABRICKS_TEST_SQL", "SELECT 1 AS n")
AWS_SQL = os.environ.get("OPENLAKEHOUSE_AWS_TEST_SQL", "SELECT 1 AS n")
DB_CATALOG = os.environ.get("OPENLAKEHOUSE_DB_CATALOG", "samples")
DB_SCHEMA = os.environ.get("OPENLAKEHOUSE_DB_SCHEMA", "nyctaxi")
AWS_CATALOG = os.environ.get("OPENLAKEHOUSE_AWS_CATALOG", "AwsDataCatalog")
AWS_SCHEMA = os.environ.get("OPENLAKEHOUSE_AWS_SCHEMA", "openlakehouse_test")

PLATFORM_SQL = {"databricks": DB_SQL, "aws": AWS_SQL}
PLATFORM_CATALOG = {"databricks": DB_CATALOG, "aws": AWS_CATALOG}
PLATFORM_SCHEMA = {"databricks": DB_SCHEMA, "aws": AWS_SCHEMA}


def _probe_query(adapter, platform: str) -> dict:
    sql = PLATFORM_SQL[platform]
    catalog = PLATFORM_CATALOG[platform]
    schema = PLATFORM_SCHEMA[platform]

    raw, ms, err = timed(adapter.execute_query, sql, catalog=catalog, schema=schema, max_rows=100)

    if err:
        return {
            "platform": platform, "adapter": adapter.name, "sql": sql,
            "canonical_shape_valid": False,
            "columns_present": False, "rows_present": False,
            "pagination_present": False, "execution_present": False,
            "columns_fields_ok": False, "pagination_fields_ok": False,
            "execution_fields_ok": False,
            "column_count": 0, "row_count": 0,
            "execution_time_ms": round(ms, 1),
            "query_id": None,
            "truncated": None, "next_page_token": None,
            "success": False, "error": err,
        }

    canonical = query_result_to_canonical(raw, adapter.name, platform, execution_time_ms=ms)
    data = canonical.model_dump()

    q_ok, q_miss = check_fields(data, CANONICAL_QUERY_FIELDS)
    p_ok, p_miss = check_fields(data.get("pagination", {}), CANONICAL_PAGINATION_FIELDS)
    e_ok, e_miss = check_fields(data.get("execution", {}), CANONICAL_EXECUTION_FIELDS)

    valid = q_ok and p_ok and e_ok

    return {
        "platform": platform,
        "adapter": adapter.name,
        "sql": sql,
        "canonical_shape_valid": valid,
        "columns_present": "columns" in data,
        "rows_present": "rows" in data,
        "pagination_present": "pagination" in data,
        "execution_present": "execution" in data,
        "columns_fields_ok": q_ok,
        "pagination_fields_ok": p_ok,
        "execution_fields_ok": e_ok,
        "column_count": len(data.get("columns", [])),
        "row_count": data.get("pagination", {}).get("row_count", 0),
        "execution_time_ms": round(data.get("execution", {}).get("execution_time_ms", 0) or 0, 1),
        "query_id": data.get("execution", {}).get("query_id"),
        "truncated": data.get("pagination", {}).get("truncated"),
        "next_page_token": data.get("pagination", {}).get("next_page_token"),
        "success": valid,
        "error": None,
        "_canonical_example": data,
    }


def run() -> dict:
    print("\n=== Experiment 2: Canonical Query Normalization ===")
    adapters, load_errors = try_load_adapters()

    rows: list[dict] = []
    skipped: list[str] = []

    for name, err in load_errors.items():
        skipped.append(f"{name}: {err}")
        print(f"  SKIP {name}: {err}")

    for name, adapter in adapters.items():
        print(f"  querying {name} ({adapter.platform}): {PLATFORM_SQL[adapter.platform]!r}...")
        row = _probe_query(adapter, adapter.platform)
        rows.append(row)
        status = "PASS" if row["success"] else f"FAIL: {row.get('error', '')}"
        print(f"    → {status} | {row['row_count']} rows | {row['execution_time_ms']} ms | query_id={row['query_id']}")

    if not rows:
        rows.append({
            "platform": "all", "adapter": "all", "sql": "-",
            "canonical_shape_valid": False,
            "success": False, "error": "No adapters loaded",
        })

    examples = {r["platform"]: r.pop("_canonical_example", None) for r in rows}

    result = {
        "experiment": "Canonical Query Normalization",
        "status": "completed" if adapters else "skipped",
        "skipped_adapters": skipped,
        "total": len(rows),
        "passed": sum(1 for r in rows if r["success"]),
        "canonical_examples": examples,
        "rows": rows,
    }

    csv_fields = [
        "platform", "adapter", "sql", "canonical_shape_valid",
        "columns_present", "rows_present", "pagination_present", "execution_present",
        "columns_fields_ok", "pagination_fields_ok", "execution_fields_ok",
        "column_count", "row_count", "execution_time_ms", "query_id",
        "truncated", "next_page_token", "success", "error",
    ]

    save_json(OUTPUT_DIR / "experiment_2_query_normalization.json", result)
    save_csv(OUTPUT_DIR / "experiment_2_query_normalization.csv", rows, csv_fields)
    save_md(OUTPUT_DIR / "experiment_2_query_normalization.md", _make_md(rows, examples, skipped))

    print(f"  Result: {result['passed']}/{result['total']} platforms passed canonical query shape")
    return result


def _make_md(rows, examples, skipped) -> str:
    table_rows = [{
        "Platform": r["platform"],
        "Adapter": r["adapter"],
        "SQL": r["sql"],
        "Shape Valid": "✓" if r.get("canonical_shape_valid") else "✗",
        "Columns": "✓" if r.get("columns_present") else "✗",
        "Pagination": "✓" if r.get("pagination_present") else "✗",
        "Execution": "✓" if r.get("execution_present") else "✗",
        "Rows": r.get("row_count", "-"),
        "Time (ms)": r.get("execution_time_ms", "-"),
        "Query ID": r.get("query_id") or "N/A",
        "Status": "PASS" if r.get("success") else "FAIL/SKIP",
    } for r in rows]

    lines = [
        "# Experiment 2 — Canonical Query Normalization",
        "",
        "## Purpose",
        "Verify that SQL queries executed against Databricks SQL Warehouse and AWS Athena "
        "return results with the same `CanonicalQueryResult` structure, including normalized "
        "column types, pagination state, and execution metadata.",
        "",
        "## Results",
        "",
        md_table(table_rows, ["Platform", "Adapter", "SQL", "Shape Valid",
                               "Columns", "Pagination", "Execution",
                               "Rows", "Time (ms)", "Query ID", "Status"]),
        "",
        "## Platform Asymmetries Normalized by CLM",
        "",
        "| Aspect | Databricks | AWS Athena | Canonical Field |",
        "|---|---|---|---|",
        "| Execution model | Synchronous cursor | Async (start→poll→fetch) | `execution.execution_time_ms` |",
        "| Query ID | None (v1) | `QueryExecutionId` UUID | `execution.query_id` |",
        "| Pagination | Not resumable | Real `NextToken` | `pagination.next_page_token` |",
        "| Header row | None | Duplicated on page 1 (stripped) | `pagination.row_count` |",
        "| Type names | `LONG`, `TIMESTAMP_NTZ` | `integer`, `varchar` | `data_type` (canonical) |",
        "",
    ]

    for platform, example in examples.items():
        if example:
            lines += [
                f"## Canonical Result Example — {platform}",
                "",
                "```json",
                __import__("json").dumps({
                    "columns": example.get("columns", [])[:2],
                    "rows": example.get("rows", [])[:2],
                    "pagination": example.get("pagination"),
                    "execution": example.get("execution"),
                }, indent=2, default=str),
                "```",
                "",
            ]

    if skipped:
        lines += ["## Skipped", ""]
        for s in skipped:
            lines.append(f"- {s}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run()
