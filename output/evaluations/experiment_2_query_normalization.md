# Experiment 2 — Canonical Query Normalization

## Research Question

Do Databricks SQL Warehouse and AWS Athena produce structurally identical query results when mediated through the CLM Query Layer, despite fundamentally different execution models (synchronous vs. asynchronous)?

## Method

Execute `SELECT 1 AS n` against live Databricks (SQL Warehouse, synchronous cursor) and AWS (Athena, asynchronous start→poll→fetch) adapters. Pass each native `QueryResult` through `query_result_to_canonical()`. Check that the `CanonicalQueryResult` envelope — `columns`, `rows`, `pagination`, `execution` — is present and complete on both platforms.

## Normalization Scope

**v1 CLM Query Layer normalizes:**
- Response envelope structure (`columns`, `rows`, `pagination`, `execution` sub-objects)
- Execution metadata (`query_id`, `execution_time_ms`, `adapter`, `platform`)
- Pagination state (`truncated`, `next_page_token`, `row_count`)
- Column type vocabulary (`CanonicalDataType` enum: STRING, INTEGER, BIGINT, etc.)

**v1 CLM does NOT normalize:**
- Scalar row value types: Athena returns all column values as strings; Databricks may return typed values. Type-level normalization of row scalars is out of scope for v1 and documented as an Implementation Note, not a conformance failure.

## Results

**Query Conformance Rate: 100% (2/2 platforms)**

| Platform | Adapter | SQL | Shape Valid | Columns | Pagination | Execution Meta | Rows | Exec Time (ms) | Query ID | Conformance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| databricks | databricks_prod | SELECT 1 AS n | ✓ | ✓ | ✓ | ✓ | 1 | 1054.5 | null | ✓ PASS |
| aws | aws_prod | SELECT 1 AS n | ✓ | ✓ | ✓ | ✓ | 1 | 1403.9 | e11db9a0-e6a9-48c5-acb1-feac8b3d409d | ✓ PASS |


> **Note on execution time:** Values shown are observed wall-clock durations including network round-trip, Athena query scheduling, and any warehouse warm-up overhead. They are reported as informational context and are not used to evaluate CLM conformance.

## Platform Asymmetries Normalized by the CLM Query Layer

| Aspect | Databricks | AWS Athena | Canonical Field |
|---|---|---|---|
| Execution model | Synchronous cursor (DB-API) | Async start → poll → fetch | `execution.execution_time_ms` |
| Query ID | `null` (connector limitation, v1) | `QueryExecutionId` UUID | `execution.query_id` |
| Pagination | Not resumable in v1 (`next_page_token=None`) | Real `NextToken` | `pagination.next_page_token` |
| Header row | Not duplicated | Duplicated on page 1 — stripped by adapter | `pagination.row_count` |
| Type vocabulary | `LONG`, `TIMESTAMP_NTZ`, `DOUBLE` | `integer`, `varchar`, `string` | `columns[].data_type` (canonical) |

## Canonical Result Example — databricks

```json
{
  "columns": [
    {
      "name": "n",
      "data_type": "integer",
      "raw_type": "int",
      "nullable": true
    }
  ],
  "rows": [
    [
      1
    ]
  ],
  "pagination": {
    "truncated": false,
    "next_page_token": null,
    "row_count": 1
  },
  "execution": {
    "query_id": null,
    "adapter": "databricks_prod",
    "platform": "databricks",
    "execution_time_ms": 1054.526702966541,
    "native_metadata": {}
  }
}
```

## Canonical Result Example — aws

```json
{
  "columns": [
    {
      "name": "n",
      "data_type": "integer",
      "raw_type": "integer",
      "nullable": true
    }
  ],
  "rows": [
    [
      "1"
    ]
  ],
  "pagination": {
    "truncated": false,
    "next_page_token": null,
    "row_count": 1
  },
  "execution": {
    "query_id": "e11db9a0-e6a9-48c5-acb1-feac8b3d409d",
    "adapter": "aws_prod",
    "platform": "aws",
    "execution_time_ms": 1403.8800077978522,
    "native_metadata": {}
  }
}
```

## Implementation Notes

The following platform-level observations were recorded. None affect CLM conformance.

1. query_id=None: The databricks-sql-connector does not expose the SQL statement ID via the DB-API cursor interface. This is a v1 connector limitation, not a CLM conformance failure. The field is present in the canonical shape; the value is null.
2. Row scalar types: Athena returns all values as strings (e.g. "1" for SELECT 1). Databricks may return typed values. Scalar type normalization is outside the CLM v1 scope — the envelope structure (columns, rows, pagination, execution) is fully normalized. This difference is recorded here as an implementation note, not a failure.

## Discussion

Both platforms produced valid `CanonicalQueryResult` envelopes with all required sub-objects. The `query_id=null` for Databricks is a known v1 connector limitation: the `databricks-sql-connector` DB-API cursor does not expose the underlying SQL statement ID. The field is present in the canonical shape with a null value, which is valid per the CLM specification. AWS Athena provides a `QueryExecutionId` which maps directly to `execution.query_id`.

The asymmetry in scalar row value types (Athena strings vs. Databricks typed values) does not affect envelope conformance. Agents consuming `CanonicalQueryResult` receive the same structure from both platforms; type coercion at the application layer is outside the CLM v1 contract.
