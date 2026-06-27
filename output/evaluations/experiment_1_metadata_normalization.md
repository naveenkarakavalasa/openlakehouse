# Experiment 1 — Canonical Metadata Normalization

## Purpose
Verify that Databricks Unity Catalog and AWS Glue Data Catalog metadata are returned through a unified Canonical Lakehouse Model (CLM) with the same structural fields, making them indistinguishable to an AI agent at the schema level.

## Conformance Summary

| Platform | Conformance |
| --- | --- |
| databricks | 4/4 operations |
| aws | 4/4 operations |


## Operation Results

| Platform | Adapter | Operation | Canonical Model | Fields OK | Count | Latency (ms) | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| databricks | databricks_prod | list_catalogs | CanonicalCatalog | ✓ | 3 | 645.5 | PASS |
| databricks | databricks_prod | list_schemas | CanonicalSchema | ✓ | 10 | 404.6 | PASS |
| databricks | databricks_prod | list_tables | CanonicalTable | ✓ | 1 | 136.7 | PASS |
| databricks | databricks_prod | describe_table | CanonicalTableSchema | ✓ | 6 | 162.0 | PASS |
| aws | aws_prod | list_catalogs | CanonicalCatalog | ✓ | 1 | 0.0 | PASS |
| aws | aws_prod | list_schemas | CanonicalSchema | ✓ | 1 | 314.6 | PASS |
| aws | aws_prod | list_tables | CanonicalTable | ✓ | 1 | 74.5 | PASS |
| aws | aws_prod | describe_table | CanonicalTableSchema | ✓ | 3 | 74.1 | PASS |


## Key Finding

Both Databricks (Unity Catalog) and AWS (Glue Data Catalog) return metadata through identical canonical fields (`adapter`, `platform`, `catalog`, `schema`, `table`, `platform_metadata`). Platform-specific identifiers (Unity Catalog 3-level namespace vs Glue Database concept) are normalized into the canonical model, with native identifiers preserved in `native_catalog` / `native_schema` fields.
