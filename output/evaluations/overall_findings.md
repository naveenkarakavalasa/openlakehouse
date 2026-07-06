# OpenLakehouse — Overall Evaluation Findings

> **Paper:** OpenLakehouse: A Canonical Semantic Interoperability Layer for AI Agent Data Virtualization

## Summary

OpenLakehouse introduces the Canonical Lakehouse Model (CLM): a three-layer semantic abstraction (Metadata Layer, Query Layer, Governance Layer) that gives AI agents unified, governed access to data across heterogeneous lakehouse platforms through a single MCP server. Five experiments evaluate whether the CLM delivers its claimed properties.

## Architectural Properties Validated

| Property | Experiment | Result | Status |
| --- | --- | --- | --- |
| CLM Metadata Layer Conformance | Exp 1 | 100% (8/8 operations) | VERIFIED |
| CLM Query Layer Conformance | Exp 2 | 100% (2/2 platforms) | VERIFIED |
| CLM Governance Layer Conformance | Exp 3 | 100% (8/8 scenarios) | VERIFIED |
| Default Deny | Exp 3 | DENIED_NO_MATCHING_RULE when no rule matches | VERIFIED |
| Last Match Wins | Exp 3 | Deny rule overrides earlier allow rule | VERIFIED |
| Policy-Before-Adapter | Exp 3 | Adapter never called on denied request (3 unit tests) | VERIFIED |
| Agent Portability (N→1 endpoints) | Exp 4 | 2→1 MCP endpoints, 2 platform branches eliminated | VERIFIED |
| Zero Agent Modification | Exp 5 | SnowflakeAdapter stub: VERIFIED | VERIFIED |


## Experiment Findings

### Experiment 1 — Canonical Metadata Normalization (Metadata Layer)

**Metadata Conformance Rate: 100% (8/8 operations)**

Databricks Unity Catalog and AWS Glue Data Catalog both produce `CanonicalCatalog`, `CanonicalSchema`, `CanonicalTable`, and `CanonicalTableSchema` objects with identical required field sets. The key namespace mapping challenge — AWS Glue has no native catalog tier — is resolved by mapping the Glue Data Catalog itself as the catalog (`AwsDataCatalog`) and Glue databases as schemas. Platform-specific identifiers are preserved in `native_catalog` and `native_schema` shadow fields.

### Experiment 2 — Canonical Query Normalization (Query Layer)

**Query Conformance Rate: 100% (2/2 platforms)**

Databricks SQL Warehouse (synchronous DB-API cursor) and AWS Athena (asynchronous start→poll→fetch) both produce the same `CanonicalQueryResult` envelope: `columns`, `rows`, `pagination`, and `execution` sub-objects. Platform asymmetries normalized: Athena's duplicated header row (stripped by adapter), differing type name vocabularies (normalized to `CanonicalDataType`), and real Athena pagination via `NextToken` vs. Databricks' non-resumable cursor (documented as a v1 limitation). The `query_id=null` for Databricks is a connector limitation, not a CLM conformance failure.

### Experiment 3 — Unified Governance Enforcement (Governance Layer)

**Governance Conformance Rate: 100% (8/8 scenarios)**

The CLM Governance Layer correctly enforced all 8 authorization scenarios across two identities (analyst, admin), two platforms (Databricks, AWS), and BROWSE/QUERY permission modes. All five `CanonicalReasonCode` values were exercised. The Policy-Before-Adapter property was verified: denied requests never reached the adapter layer (confirmed by 3 unit tests with mock adapter). Governance is platform-independent — the same `policy.yaml` governs Databricks and AWS resources uniformly.

### Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling (Architecture)

Static analysis comparing four integration approaches shows that OpenLakehouse CLM reduces agent integration complexity relative to native multi-MCP integration:

- MCP endpoints: 2 → 1 (1 eliminated)
- Platform-specific code branches in agent: 2 → 0 (2 eliminated)
- Response model variants: 2 → 1
- Governance models: 2 → 1 (unified policy.yaml)
- Agent code changes when adding a new platform: zero

Vendor lock-in is reduced (not eliminated): the agent is coupled to the CLM contract rather than to platform-specific APIs, substantially lowering platform migration risk.

### Experiment 5 — Platform Extension Property Validation (Architecture)

**Zero Agent Modification Property: VERIFIED**

A concrete `SnowflakeAdapter` stub was created and verified. It implements the `LakehouseAdapter` ABC without modifying any core module; the existing canonical mapper functions produced valid output for all five adapter operations. Adding a new platform to OpenLakehouse requires exactly 4 component changes: 1 new adapter file, 3 minor edits (config model, registry, config YAML). Agent code, MCP tool names, canonical models, and the policy engine are unchanged.

Measured adapter sizes: databricks: 139 LOC | aws: 220 LOC. Average: 179 LOC. This establishes an empirical upper bound for the effort to add a new platform.

## Key Quantitative Findings

| Metric | Value |
|---|---|
| Platforms unified | 2 (Databricks Unity Catalog + AWS Glue/Athena) |
| CLM Layers | 3 (Metadata, Query, Governance) |
| MCP tools (agent-facing) | 5 — unchanged across platforms |
| Metadata Conformance Rate | 100% (8/8 operations) |
| Query Conformance Rate | 100% (2/2 platforms) |
| Governance Conformance Rate | 100% (8/8 scenarios) |
| Governance reason codes | 5 (structured, machine-readable) |
| MCP endpoints (CLM vs native multi) | 1 vs 2 (1 eliminated) |
| Platform branches in agent (CLM vs native multi) | 0 vs 2 (2 eliminated) |
| Agent code changes when adding platform | 0 |
| Components changed to add platform | 4 (1 new, 3 edits) |
| Zero Agent Modification Property | VERIFIED |
| Unit tests | 89 passed, 4 warnings in 3.13s |

## Platform Capability Comparison

| Capability | Databricks Native | AWS Native | Native Multi-MCP | OpenLakehouse CLM |
| --- | --- | --- | --- | --- |
| Multi-platform data access | No — Databricks only | No — AWS only | Yes — but agent must handle N endpoints | Yes — single endpoint, platform-transparent |
| Canonical Metadata (CLM) | No — Unity Catalog schema | No — Glue API schema | No — mixed schemas | Yes — CanonicalCatalog / Schema / Table |
| Canonical Queries (CLM) | No — DB-API / SQL Warehouse specific | No — Athena QueryResult specific | No — mixed result shapes | Yes — CanonicalQueryResult |
| Unified Governance | No — Unity Catalog GRANT SQL | No — IAM + Lake Formation | No — separate per platform | Yes — single policy.yaml for all platforms |
| Unified Semantic Contract | No | No | No | Yes — stable canonical fields across platforms |
| Single MCP Endpoint | Yes (1 platform) | Yes (1 platform) | No — N endpoints for N platforms | Yes — 1 endpoint for all platforms |
| Zero Agent Modification on Platform Add | N/A | N/A | No — agent change required | Yes — VERIFIED (Experiment 5) |


## Limitations

1. **Databricks query pagination:** Not resumable in v1. The `databricks-sql-connector` DB-API cursor does not expose a server-side resumable cursor. Truncated results have `next_page_token=None`. Workaround: narrow queries with LIMIT/WHERE.

2. **Scalar row type normalization:** CLM v1 normalizes the response envelope structure but not scalar row value types. Athena returns all values as strings; Databricks returns typed values. Type coercion is left to the consuming agent.

3. **SQL guard is a heuristic:** `assert_read_only()` uses a denylist/allowlist, not a full SQL parser. Run adapters with read-only platform grants as defense in depth.

4. **AWS Lake Formation is rely-and-surface:** OpenLakehouse does not proactively introspect Lake Formation grants. If LF denies an IAM principal, the boto3 call fails with `AccessDeniedException`, which maps to `PermissionDeniedError`. Combine LF with the OpenLakehouse policy layer for full coverage.

5. **SnowflakeAdapter is an architectural stub:** Experiment 5 validates the extension pattern; a production Snowflake adapter would require `snowflake-connector-python` and handle real authentication, pagination, and type mapping.

6. **v1 identity model:** Identity is resolved once per server process from `OPENLAKEHOUSE_IDENTITY` env var. Per-request identity is a v2 consideration.

## Paper-Ready Conclusions

We evaluated OpenLakehouse across five experiments targeting the three CLM layers and two architectural properties.

**Experiment 1** confirmed that Databricks Unity Catalog and AWS Glue Data Catalog metadata are exposed through structurally identical canonical objects (CanonicalCatalog, CanonicalSchema, CanonicalTable), with platform-specific identifiers preserved in native shadow fields. Metadata Conformance Rate: 100% (8/8 operations).

**Experiment 2** confirmed that SQL queries against Databricks SQL Warehouse and AWS Athena — despite fundamentally different execution models — produce the same CanonicalQueryResult envelope structure with normalized column types, pagination state, and per-platform execution metadata. Query Conformance Rate: 100% (2/2 platforms).

**Experiment 3** validated the CLM Governance Layer across 8 authorization scenarios, confirming default-deny semantics, last-match-wins rule evaluation, five structured reason codes, Browse/Query permission separation, and the Policy-Before-Adapter property. Governance Conformance Rate: 100% (8/8 scenarios). Governance decisions are platform-independent.

**Experiment 4** showed that OpenLakehouse reduces agent coupling from N MCP endpoints and N platform-specific parsers to a single endpoint and a single canonical parser, eliminating all platform branches from agent code and unifying governance into one policy file.

**Experiment 5** verified the Zero Agent Modification Property: adding a third platform (demonstrated with a SnowflakeAdapter stub) required exactly 4 component changes and zero agent-side modifications. Status: VERIFIED.
