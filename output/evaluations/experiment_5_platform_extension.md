# Experiment 5 — Platform Extension Property Validation

## Research Question

Can a new lakehouse platform be added to OpenLakehouse with zero changes to agent code, MCP tool names, canonical models, or the policy engine — and does the existing canonical mapper produce correct output for the new adapter without modification?

## Method

1. Measure LOC and public methods of the existing production adapters to establish an empirical size baseline.
2. Create a concrete `SnowflakeAdapter` stub that implements `LakehouseAdapter` ABC without modifying any core module.
3. Dynamically load and exercise the stub: call all five adapter methods, pass output through the existing canonical mapper functions, verify structural correctness.
4. Enumerate components changed vs. unchanged to prove the Zero Agent Modification Property.

**Note:** The SnowflakeAdapter is an architectural validation stub. It demonstrates the extension pattern but is NOT a production Snowflake implementation — real `snowflake-connector-python` calls are replaced with hardcoded return values.

## Existing Adapter Baseline (Measured)

| Platform | File | LOC (measured) | Public Methods |
| --- | --- | --- | --- |
| databricks | src/openlakehouse/adapters/databricks_adapter.py | 139 | 5 |
| aws | src/openlakehouse/adapters/aws_adapter.py | 220 | 5 |


Average production adapter size: **179 LOC**

## Components Changed When Adding SnowflakeAdapter

| Component | Change | Purpose | Agent Impact | MCP Tools Impact | Canonical Impact |
| --- | --- | --- | --- | --- | --- |
| src/openlakehouse/adapters/snowflake_adapter.py | NEW FILE | Implement LakehouseAdapter ABC for Snowflake | None | None | None |
| src/openlakehouse/config/models.py | MINOR EDIT | Add SnowflakeAdapterConfig Pydantic model | None | None | None |
| src/openlakehouse/adapters/registry.py | MINOR EDIT | Add elif branch for SnowflakeAdapterConfig | None | None | None |
| config/config.yaml | MINOR EDIT | Add snowflake_prod adapter block with connection parameters | None | None | None |


## Components Unchanged (Zero Agent Modification Property)

| Component | Status | Description |
| --- | --- | --- |
| server/tools.py | UNCHANGED | Five MCP tools — names, parameters, and return types unchanged |
| core/canonical/metadata.py | UNCHANGED | CanonicalCatalog, CanonicalSchema, CanonicalTable, CanonicalTableSchema |
| core/canonical/query.py | UNCHANGED | CanonicalQueryResult, CanonicalQueryColumn, CanonicalPagination, CanonicalExecutionMetadata |
| core/canonical/governance.py | UNCHANGED | CanonicalPolicy, CanonicalAuthorizationDecision, CanonicalReasonCode |
| core/canonical/mapper.py | UNCHANGED | All mapper functions reused unchanged by the new adapter |
| policy/engine.py | UNCHANGED | PolicyEngine unchanged — CanonicalResourceScope handles new adapter name |
| identity/resolver.py | UNCHANGED | Identity resolution unchanged |


## SnowflakeAdapter Stub Verification

**Status: VERIFIED**

The stub was dynamically loaded and all five adapter operations were exercised through the existing canonical mapper:

| Operation | Canonical Output | Platform Field |
| --- | --- | --- |
| list_catalogs | ✓ | snowflake |
| list_schemas | ✓ | snowflake |
| list_tables | ✓ | snowflake |
| describe_table | ✓ | snowflake |
| execute_query | ✓ | snowflake |


All canonical mapper functions (`catalog_to_canonical`, `schema_to_canonical`, `table_summary_to_canonical`, `table_schema_to_canonical`, `query_result_to_canonical`) produced valid output for Snowflake without any modification.

## Discussion

The SnowflakeAdapter stub confirms the architectural property: the `LakehouseAdapter` ABC and canonical mapper form a stable extension point. Adding a new platform:

- Does NOT require changes to `server/tools.py` (same 5 tools, same parameters)
- Does NOT require changes to canonical models (same CanonicalCatalog, CanonicalTable, etc.)
- Does NOT require changes to the policy engine (`CanonicalResourceScope` handles the new adapter name via config)
- Does NOT require any agent-side code changes

An AI agent already connected to OpenLakehouse would automatically discover Snowflake catalogs through `list_catalogs`, explore schemas and tables through `list_schemas` / `list_tables`, and receive `CanonicalQueryResult` from `run_query` — with zero code changes on the agent side.

The size of a new adapter is empirically bounded by the existing adapters: 179 LOC average. This work is entirely server-side and requires no coordination with agent developers.
