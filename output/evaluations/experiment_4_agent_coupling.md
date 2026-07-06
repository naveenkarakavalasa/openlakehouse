# Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling

## Research Question

How does agent integration complexity compare between native platform connectors and the OpenLakehouse Canonical Lakehouse Model (CLM) when an agent must access data across multiple lakehouse platforms?

## Method

Static analysis comparing four integration approaches across six coupling dimensions. Agent Portability Metrics quantify the reduction in agent-side work when moving from native multi-platform integration (Approach C) to the OpenLakehouse CLM (Approach D).

## Agent Portability Metrics

| Metric | Native Multi-MCP | OpenLakehouse CLM | Improvement |
| --- | --- | --- | --- |
| MCP endpoints | 2 | 1 | −1 |
| Response model variants | 2 | 1 | −1 |
| Agent response parsers | 2 | 1 | −1 |
| Platform-specific code branches | 2 | 0 | −2 |
| Governance models required | 2 | 1 | −1 |
| Agent code changes when adding platform | High — new endpoint + parser + branches | Zero — server-side adapter only | Full elimination |


## Approach Comparison

| Approach | MCP Endpoints | Response Models | Platform Branches | Unified Contract | Supports Both | Vendor Lock-in |
| --- | --- | --- | --- | --- | --- | --- |
| A — Databricks Native | 1 | 1 | 0 | ✗ | ✗ | High |
| B — AWS Native | 1 | 1 | 0 | ✗ | ✗ | High |
| C — Native Multi-MCP | 2 | 2 | 2 | ✗ | ✗ | High (multiplied; grows linearly with platform count) |
| D — OpenLakehouse CLM | 1 | 1 | 0 | ✓ | ✓ | Reduced |


## Capability Comparison by Tool

| Capability | Databricks Native | AWS Native | OpenLakehouse CLM |
| --- | --- | --- | --- |
| list_catalogs | catalog.list() → DatabricksCatalogInfo[] | glue.get_databases() → DatabaseList[] | list_catalogs() → CanonicalCatalog[] (same shape, both platforms) |
| list_tables | tables.list() → TableInfo[] | glue.get_tables() → TableList[] | list_tables() → CanonicalTable[] (same shape, both platforms) |
| run_query | cursor.execute() → DB-API Row[] | athena.start_query_execution() → async poll → Rows[] | run_query() → CanonicalQueryResult (same shape, both platforms) |
| Governance | UC GRANT SQL (per-catalog, Databricks-specific) | IAM + Lake Formation (per-database, AWS-specific) | CanonicalPolicy YAML — adapter/catalog/schema/table rules, unified |
| Unified Semantic Contract | No — agent tied to Databricks API schema | No — agent tied to AWS API schema | Yes — CLM defines stable canonical fields independent of platform |


## Discussion

Under native multi-MCP integration (Approach C), every new platform multiplies agent complexity: additional MCP endpoint configuration, additional response schema parsers, and additional platform-specific branches in agent code. Governance is also fragmented across platform-native permission systems (Databricks Unity Catalog GRANT SQL, AWS IAM + Lake Formation) with no unified audit trail.

Under OpenLakehouse CLM (Approach D), all platform-specific complexity is contained server-side in the adapter layer. The agent always receives `CanonicalCatalog`, `CanonicalTable`, and `CanonicalQueryResult` shapes regardless of which platform the data resides on. Adding a third platform (e.g. Snowflake, Hive) requires zero agent code changes — verified in Experiment 5.

**Vendor lock-in is reduced, not eliminated:** The agent is now coupled to the CLM contract rather than platform-specific schemas. The CLM is an open internal abstraction (not a proprietary cloud vendor API), so platform migration risk is substantially reduced — but the agent does depend on OpenLakehouse as an intermediary layer.

## Zero-Agent-Modification Property

When a new platform adapter is added to OpenLakehouse server-side:
- Agent MCP config: **unchanged** (same single endpoint)
- Agent response parsing: **unchanged** (same canonical models)
- Agent tool call code: **unchanged** (same 5 tool names, same parameters)
- Unified governance policy: **unchanged** (same policy.yaml syntax)

Formally verified in Experiment 5 using a concrete SnowflakeAdapter stub.
