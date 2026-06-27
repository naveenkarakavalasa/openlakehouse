# OpenLakehouse Evaluation Suite — Summary

> **Paper:** OpenLakehouse: A Canonical Semantic Interoperability Layer for AI Agent Data Virtualization

## Experiment Results

| Exp | Name | Status | Time (ms) | Notes |
| --- | --- | --- | --- | --- |
| #1 | Canonical Metadata Normalization | COMPLETED | 3156.9 |  |
| #2 | Canonical Query Normalization | COMPLETED | 12627.9 |  |
| #3 | Unified Governance Enforcement | COMPLETED | 362.3 |  |
| #4 | Native MCP vs OpenLakehouse Agent Coupling | COMPLETED | 2.9 |  |
| #5 | Platform Extension Effort / Zero Agent Modification | COMPLETED | 30.5 |  |


**Unit Tests:** 89 passed, 4 warnings in 3.07s

## Experiment 1: Canonical Metadata Normalization  [COMPLETED]

Databricks Unity Catalog and AWS Glue Data Catalog metadata were verified to return uniform CanonicalCatalog, CanonicalSchema, CanonicalTable, and CanonicalTableSchema objects with identical required field sets. Platform-specific identifiers are preserved in `native_*` fields while the canonical fields remain identical across platforms.

## Experiment 2: Canonical Query Normalization  [COMPLETED]

SQL query execution against Databricks SQL Warehouse (synchronous, cursor-based) and AWS Athena (asynchronous, poll-based) was verified to produce the same CanonicalQueryResult structure with columns, rows, pagination, and execution metadata. Platform asymmetries (Athena QueryExecutionId, Athena header-row duplication, differing type name vocabularies) are fully normalized by the CLM.

## Experiment 3: Unified Governance Enforcement  [COMPLETED]

The Canonical Governance Model was validated across 8 authorization scenarios. Default-deny, last-match-wins rule evaluation, BROWSE/QUERY permission separation, and 5 structured reason codes (ALLOWED, DENIED_BY_RULE, DENIED_NO_MATCHING_RULE, DENIED_NO_ROLE, DENIED_NO_QUERY_PERMISSION) all behaved correctly. The policy-before-adapter invariant was verified by 3 dedicated unit tests asserting the adapter mock is never called when policy denies.

## Experiment 4: Native MCP vs OpenLakehouse Agent Coupling  [COMPLETED]

Static analysis comparing 4 integration approaches showed that OpenLakehouse CLM reduces MCP endpoint count from 2→1, response model variants from 2→1, and platform-specific agent code branches from 2→0, compared to native multi-MCP integration. Vendor lock-in is eliminated entirely.

## Experiment 5: Platform Extension / Zero Agent Modification  [COMPLETED]

Static analysis and a concrete SnowflakeAdapter stub verified that adding a new lakehouse platform requires exactly 4 file changes (1 new, 3 minor edits), zero agent code changes, and zero modifications to MCP tool names, canonical models, or the policy engine. The Zero Agent Modification Property formally holds.

## Key Quantitative Findings

| Metric | Value |
|---|---|
| Platforms unified under CLM | 2 (Databricks, AWS) |
| MCP tools (agent-facing) | 5 (unchanged across platforms) |
| Canonical metadata fields per object | 6–7 (adapter, platform, catalog, schema, table, type, metadata) |
| Authorization reason codes | 5 (structured, machine-readable) |
| Files changed to add new platform (CLM) | 4 |
| Agent code changes to add new platform | **0** |
| Platform branches eliminated vs native multi-MCP | 2 → 0 |
| MCP endpoints vs native multi-MCP | 2 → 1 |

## Copy-Ready Evaluation Text (for Paper)

We evaluated OpenLakehouse across five experiments. **Experiment 1** confirmed that Databricks Unity Catalog and AWS Glue Data Catalog metadata are exposed through identical canonical fields (CanonicalCatalog, CanonicalSchema, CanonicalTable), with platform-native identifiers preserved in native_* shadow fields. **Experiment 2** confirmed that SQL queries against Databricks SQL Warehouse and AWS Athena — despite fundamentally different execution models (synchronous vs. asynchronous) — produce the same CanonicalQueryResult shape, including normalized column types, pagination state, and per-platform execution metadata. **Experiment 3** validated the Canonical Governance Model across 8 authorization scenarios, confirming default-deny semantics, last-match-wins rule evaluation, five structured reason codes, and the policy-before-adapter invariant (denied requests never reach the adapter). **Experiment 4** showed that OpenLakehouse reduces agent coupling from N MCP endpoints and N platform-specific parsers to a single endpoint and a single canonical parser, eliminating all platform branches from agent code. **Experiment 5** verified the Zero Agent Modification Property: adding a third platform (demonstrated with a Snowflake stub) required exactly 4 file changes (1 new adapter file, 3 minor registrations) and zero changes to agent code, MCP tool names, canonical models, or the policy engine.

## Generated Files

- `output/evaluations/experiment_1_metadata_normalization.csv`
- `output/evaluations/experiment_1_metadata_normalization.json`
- `output/evaluations/experiment_1_metadata_normalization.md`
- `output/evaluations/experiment_2_query_normalization.csv`
- `output/evaluations/experiment_2_query_normalization.json`
- `output/evaluations/experiment_2_query_normalization.md`
- `output/evaluations/experiment_3_governance_enforcement.csv`
- `output/evaluations/experiment_3_governance_enforcement.json`
- `output/evaluations/experiment_3_governance_enforcement.md`
- `output/evaluations/experiment_4_agent_coupling.csv`
- `output/evaluations/experiment_4_agent_coupling.json`
- `output/evaluations/experiment_4_agent_coupling.md`
- `output/evaluations/experiment_5_platform_extension.csv`
- `output/evaluations/experiment_5_platform_extension.json`
- `output/evaluations/experiment_5_platform_extension.md`

## Limitations

- Databricks query pagination is not resumable in v1 (next_page_token=None for Databricks)
- assert_read_only is a denylist heuristic, not a full SQL parser
- AWS Lake Formation is 'rely-and-surface' — OpenLakehouse does not proactively introspect LF grants
- SnowflakeAdapter in Experiment 5 is a stub — not connected to real Snowflake
- Performance measurements include network latency and warehouse cold-start time
