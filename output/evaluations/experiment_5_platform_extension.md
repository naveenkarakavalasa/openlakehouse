# Experiment 5 — Platform Extension Effort / Zero Agent Modification Property

## Purpose
Measure and verify the effort required to add a new lakehouse platform (Snowflake) to OpenLakehouse vs. native agent integration. Formally verifies the Zero Agent Modification Property: adding a platform adapter requires zero changes to agent code, MCP tool names, canonical models, or response parsers.

## Existing Adapter Baseline

| Platform | File | LOC | Public Methods |
| --- | --- | --- | --- |
| databricks | src/openlakehouse/adapters/databricks_adapter.py | 139 | 5 |
| aws | src/openlakehouse/adapters/aws_adapter.py | 220 | 5 |


## Extension Effort Comparison

| Approach | New Files | Agent LOC Added | Total LOC Added | Agent Code Changes | MCP Tool Changes | Zero Mod Property |
| --- | --- | --- | --- | --- | --- | --- |
| A — Native Agent Integration | 0 | 300 | 300 | Required | N/A — agent owns the tools | ✗ N/A |
| B — OpenLakehouse CLM Adapter | 4 | 0 | 179 | None | None — server/tools.py unchanged | ✓ HOLDS |


## Files Changed When Adding SnowflakeAdapter (CLM approach)

| File | Purpose | Touches Agent | Touches MCP Tools | Touches Canonical | New File |
| --- | --- | --- | --- | --- | --- |
| src/openlakehouse/adapters/snowflake_adapter.py | Implement LakehouseAdapter for Snowflake | ✗ | ✗ | ✗ | NEW |
| src/openlakehouse/config/models.py | Add SnowflakeAdapterConfig Pydantic model | ✗ | ✗ | ✗ | minor edit |
| src/openlakehouse/adapters/registry.py | Add elif branch for SnowflakeAdapterConfig | ✗ | ✗ | ✗ | minor edit |
| config/config.yaml | Add snowflake_prod adapter block | ✗ | ✗ | ✗ | minor edit |


## Files Unchanged (Zero Agent Modification Property)

- `server/tools.py` — **unchanged**
- `core/canonical/metadata.py` — **unchanged**
- `core/canonical/query.py` — **unchanged**
- `core/canonical/governance.py` — **unchanged**
- `core/canonical/mapper.py` — **unchanged**
- `policy/engine.py` — **unchanged**
- `identity/resolver.py` — **unchanged**

## SnowflakeAdapter Stub Verification

A concrete `SnowflakeAdapter` stub was created and verified to:
1. Implement `LakehouseAdapter` ABC without modifying any core module
2. Produce canonical metadata objects via the existing mapper
3. Produce `CanonicalQueryResult` via the existing mapper

| Operation | Canonical Output | Platform Field |
| --- | --- | --- |
| list_catalogs | ✓ | snowflake |
| list_schemas | ✓ | snowflake |
| list_tables | ✓ | snowflake |
| describe_table | ✓ | snowflake |
| execute_query | ✓ | snowflake |


**Zero Agent Modification Property: ✓ HOLDS**

An AI agent already connected to OpenLakehouse would automatically discover Snowflake catalogs through `list_catalogs`, query Snowflake tables via `run_query`, and receive the same `CanonicalQueryResult` shape — with no code changes on the agent side.
