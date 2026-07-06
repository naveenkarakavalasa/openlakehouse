# Canonical Interface Demo

> **The same Python call — `adapter.execute_query(SQL)` followed by
> `query_result_to_canonical(raw, adapter.name, adapter.platform)` —
> produces a `CanonicalQueryResult` with identical structure on every platform.**

## Platforms

- **Databricks** (databricks_prod): 🟢 live
- **AWS** (aws_prod): 🟢 live
- **Snowflake** (snowflake_stub): 🟡 stub

## Agent Call Pattern (identical for all platforms)

```python
SQL = "SELECT 1 AS n"

# Same three lines regardless of platform:
raw    = adapter.execute_query(SQL, catalog=catalog, schema=schema)
result = query_result_to_canonical(raw, adapter.name, adapter.platform)
# result: CanonicalQueryResult — shape is always the same

# Via MCP tools (same tool name, same parameters):
run_query(adapter="databricks_prod", sql=SQL)
run_query(adapter="aws_prod",        sql=SQL)
run_query(adapter="snowflake_prod",  sql=SQL)
```

## Query Result Comparison: `SELECT 1 AS n`

Bold fields (✓) are **canonical** — identical across all platforms.
Italic fields are platform-specific but always present in the same envelope.

| Field                      | Databricks (live) | AWS (live)                             | Snowflake (STUB) |
| -------------------------- | ----------------- | -------------------------------------- | ---------------- |
| **columns[0].name** ✓      | 'n'               | 'n'                                    | 'n'              |
| **columns[0].data_type** ✓ | integer           | integer                                | integer          |
| rows[0]                    | [1]               | ["1"]                                  | [1]              |
| **pagination.row_count** ✓ | 1                 | 1                                      | 1                |
| **pagination.truncated** ✓ | False             | False                                  | False            |
| _execution.platform_       | 'databricks'      | 'aws'                                  | 'snowflake'      |
| _execution.query_id_       | None              | '8cc7a5ec-c1d6-4a65-9ef7-9513b396a753' | None             |
| _execution.time_ms_        | 1125 ms           | 1449 ms                                | 0 ms             |

> **Note on `rows[0]`:** Athena returns all scalar values as strings
> (e.g. `["1"]` for `SELECT 1`). Databricks returns typed values (`[1]`).
> Scalar row type normalization is outside CLM v1 scope; the envelope
> structure is fully canonical.

> **Note on `execution.query_id`:** The `databricks-sql-connector` does
> not expose the underlying SQL statement ID via the DB-API cursor
> (v1 connector limitation). The field is present in the canonical
> shape with `null`, which is valid per the CLM specification.

## Catalog Metadata Comparison: `list_catalogs()`

The `adapter` and `platform` fields differ by design; all other canonical
fields (`catalog`, `native_catalog`, `platform_metadata`) are present on
every platform.

| Field             | Databricks (live) | AWS (live)       | Snowflake (STUB)        |
| ----------------- | ----------------- | ---------------- | ----------------------- |
| catalog name      | 'system'          | 'AwsDataCatalog' | 'SNOWFLAKE_SAMPLE_DATA' |
| platform field    | 'databricks'      | 'aws'            | 'snowflake'             |
| adapter field     | 'databricks_prod' | 'aws_prod'       | 'snowflake_stub'        |
| native_catalog    | 'system'          | 'AwsDataCatalog' | 'SNOWFLAKE_SAMPLE_DATA' |
| platform_metadata | {}                | {}               | {}                      |

## What This Demonstrates

1. **Canonical Query Layer**: `CanonicalQueryResult` has the same four
   sub-objects (`columns`, `rows`, `pagination`, `execution`) regardless
   of whether the query ran on a synchronous Databricks cursor, an
   asynchronous Athena job, or a Snowflake connector.

2. **Zero Agent Modification Property**: Adding Snowflake required only a
   new adapter class. The `query_result_to_canonical` mapper, the MCP tools,
   and the policy engine are all unchanged.

3. **Uniform Governance**: The same `policy.yaml` rule syntax controls access
   to all three platforms — no platform-specific permission model required.

## Running This Demo

```bash
# Without live credentials (Snowflake stub only):
python experiments/canonical_interface_demo.py

# With Databricks + AWS credentials:
set -a && source .env && set +a
python experiments/canonical_interface_demo.py
```
