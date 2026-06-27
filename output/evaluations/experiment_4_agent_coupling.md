# Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling

## Purpose
Compare agent integration complexity between native platform MCP connectors and the OpenLakehouse Canonical Lakehouse Model (CLM) approach. Quantifies reduction in MCP endpoints, response model variants, and platform-specific agent code branches.

## Coupling Comparison

| Approach | MCP Endpoints | Response Models | Platform Branches | Supports Both | Vendor Lock-in |
| --- | --- | --- | --- | --- | --- |
| A — Databricks Native | 1 | 1 | 0 | ✗ | High |
| B — AWS Native | 1 | 1 | 0 | ✗ | High |
| C — Native Multi-MCP | 2 | 2 | 2 | ✗ | High |
| D — OpenLakehouse CLM | 1 | 1 | 0 | ✓ | None |


## API Surface Comparison

| Tool / Concern | Databricks Native | AWS Native | OpenLakehouse CLM |
| --- | --- | --- | --- |
| list_catalogs | catalog.list() → DatabricksCatalogInfo[] | glue.get_databases() → DatabaseList[] | list_catalogs() → CanonicalCatalog[] (same shape, both platforms) |
| list_tables | tables.list() → TableInfo[] | glue.get_tables() → TableList[] | list_tables() → CanonicalTable[] (same shape, both platforms) |
| run_query | cursor.execute() → DB-API Row[] | athena.start_query_execution() → async poll → Rows[] | run_query() → CanonicalQueryResult (same shape, both platforms) |
| governance | UC privileges (GRANT SQL), per-catalog | IAM + Lake Formation, per-database | CanonicalPolicy YAML — adapter/catalog/schema/table rules, unified |


## Coupling Reduction (Native Multi-MCP → OpenLakehouse CLM)

| Metric | Native Multi-MCP | OpenLakehouse CLM | Reduction |
|---|---|---|---|
| MCP endpoints | 2 | 1 | **1** |
| Response models | 2 | 1 | **1** |
| Response parsers | 2 | 1 | **1** |
| Platform branches in agent | 2 | 0 | **2** |

## Zero-Agent-Modification Property

When a new platform adapter is added to OpenLakehouse:
- Agent MCP config: **unchanged** (same single endpoint)
- Agent response parsing: **unchanged** (same canonical model)
- Agent tool call code: **unchanged** (same 5 tool names)
- Only changed: one new adapter file + config registration (server-side only)

This property is formally verified in Experiment 5.
