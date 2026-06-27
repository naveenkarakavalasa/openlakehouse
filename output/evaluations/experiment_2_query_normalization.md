# Experiment 2 — Canonical Query Normalization

## Purpose
Verify that SQL queries executed against Databricks SQL Warehouse and AWS Athena return results with the same `CanonicalQueryResult` structure, including normalized column types, pagination state, and execution metadata.

## Results

| Platform | Adapter | SQL | Shape Valid | Columns | Pagination | Execution | Rows | Time (ms) | Query ID | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| databricks | databricks_prod | SELECT 1 AS n | ✓ | ✓ | ✓ | ✓ | 1 | 11003.4 | N/A | PASS |
| aws | aws_prod | SELECT 1 AS n | ✓ | ✓ | ✓ | ✓ | 1 | 1471.3 | 9b03314e-1e7f-4131-9382-0f63141be933 | PASS |


## Platform Asymmetries Normalized by CLM

| Aspect | Databricks | AWS Athena | Canonical Field |
|---|---|---|---|
| Execution model | Synchronous cursor | Async (start→poll→fetch) | `execution.execution_time_ms` |
| Query ID | None (v1) | `QueryExecutionId` UUID | `execution.query_id` |
| Pagination | Not resumable | Real `NextToken` | `pagination.next_page_token` |
| Header row | None | Duplicated on page 1 (stripped) | `pagination.row_count` |
| Type names | `LONG`, `TIMESTAMP_NTZ` | `integer`, `varchar` | `data_type` (canonical) |

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
    "execution_time_ms": 11003.369577927515,
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
    "query_id": "9b03314e-1e7f-4131-9382-0f63141be933",
    "adapter": "aws_prod",
    "platform": "aws",
    "execution_time_ms": 1471.3354860432446,
    "native_metadata": {}
  }
}
```

