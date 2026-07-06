# Experiment 1 — Canonical Metadata Normalization

## Research Question

Do Databricks Unity Catalog and AWS Glue Data Catalog produce structurally identical metadata when mediated through the CLM Metadata Layer?

## Method

Execute `list_catalogs`, `list_schemas`, `list_tables`, and `describe_table` against live Databricks (Unity Catalog) and AWS (Glue Data Catalog) adapters. Pass each native response through the CLM mapper functions (`catalog_to_canonical`, `schema_to_canonical`, `table_summary_to_canonical`, `table_schema_to_canonical`). Verify that every required canonical field is present in the output. Platform-specific values in `native_*` shadow fields are preserved but outside the conformance check.

**Canonical models evaluated:** CanonicalCatalog · CanonicalSchema · CanonicalTable · CanonicalTableSchema

## Results

**Metadata Conformance Rate: 100% (8/8 operations)**

### Cross-Platform Conformance by Operation

| Operation | Databricks | AWS | Canonical Model | Conformance |
| --- | --- | --- | --- | --- |
| list_catalogs | ✓ | ✓ | CanonicalCatalog | ✓ PASS |
| list_schemas | ✓ | ✓ | CanonicalSchema | ✓ PASS |
| list_tables | ✓ | ✓ | CanonicalTable | ✓ PASS |
| describe_table | ✓ | ✓ | CanonicalTableSchema | ✓ PASS |


### Per-Platform Conformance

| Platform | Conformance |
| --- | --- |
| databricks | 4/4 operations |
| aws | 4/4 operations |


### Detailed Operation Results

| Platform | Adapter | Operation | Canonical Model | Canonical Conformance | Count | Status |
| --- | --- | --- | --- | --- | --- | --- |
| databricks | databricks_prod | list_catalogs | CanonicalCatalog | ✓ | 3 | PASS |
| databricks | databricks_prod | list_schemas | CanonicalSchema | ✓ | 10 | PASS |
| databricks | databricks_prod | list_tables | CanonicalTable | ✓ | 1 | PASS |
| databricks | databricks_prod | describe_table | CanonicalTableSchema | ✓ | 6 | PASS |
| aws | aws_prod | list_catalogs | CanonicalCatalog | ✓ | 1 | PASS |
| aws | aws_prod | list_schemas | CanonicalSchema | ✓ | 1 | PASS |
| aws | aws_prod | list_tables | CanonicalTable | ✓ | 1 | PASS |
| aws | aws_prod | describe_table | CanonicalTableSchema | ✓ | 3 | PASS |


> **Note on latency:** API call durations are observed values that include network round-trip, platform processing, and any warehouse warm-up time. They are reported as informational context only and are not used to evaluate CLM conformance.

## Native → Canonical Field Mapping (Metadata Layer)

The following table shows how platform-native field names map to CLM canonical fields.

| CLM Field | Databricks Native | AWS Native | Layer |
| --- | --- | --- | --- |
| adapter | WorkspaceClient name (config key) | boto3 client name (config key) | Metadata |
| platform | "databricks" (fixed string) | "aws" (fixed string) | Metadata |
| catalog | CatalogInfo.name (Unity Catalog) | catalog_name config value (e.g. AwsDataCatalog) | Metadata |
| native_catalog | CatalogInfo.full_name | Same as catalog (no sub-catalog concept) | Metadata |
| schema | SchemaInfo.name | Glue DatabaseName | Metadata |
| native_schema | SchemaInfo.full_name | Glue DatabaseName | Metadata |
| table | TableInfo.name | Glue Table.Name | Metadata |
| table_type | TableInfo.table_type enum | Glue Table.TableType string | Metadata |
| comment | TableInfo.comment | Glue Table.Description | Metadata |
| platform_metadata | Extra Unity Catalog fields (owner, full_name, etc.) | Extra Glue fields (location, serde, etc.) | Metadata |


## Discussion

Both Databricks (Unity Catalog) and AWS (Glue Data Catalog) return metadata through identical canonical fields (`adapter`, `platform`, `catalog`, `schema`, `table`, `table_type`, `comment`, `platform_metadata`). The key namespace mapping challenges resolved by the Metadata Layer are:

- **Catalog tier:** Databricks has a native 3-level namespace (catalog.schema.table). AWS Glue has no catalog tier — the CLM maps the Glue Data Catalog itself as the catalog (named `AwsDataCatalog` by Athena convention) and Glue databases as schemas.

- **Native identifiers preserved:** Unity Catalog full names (e.g. `samples.nyctaxi.trips`) and Glue resource ARNs are preserved in `native_catalog` / `native_schema` shadow fields so no information is lost, while the canonical fields remain identical across platforms.

- **Type vocabulary:** Column types use `CanonicalDataType` (STRING, INTEGER, BIGINT, etc.) normalized from Databricks SDK enums and Glue string type names via platform-specific type maps.
