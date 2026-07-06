# OpenLakehouse Evaluation Suite — Summary

> **Paper:** OpenLakehouse: A Canonical Semantic Interoperability Layer for AI Agent Data Virtualization

## Experiment Results

| Exp | Name | CLM Layer | Status | Time (ms) | Notes |
| --- | --- | --- | --- | --- | --- |
| #1 | Canonical Metadata Normalization | Metadata Layer | COMPLETED | 2288.1 |  |
| #2 | Canonical Query Normalization | Query Layer | COMPLETED | 2607.8 |  |
| #3 | Unified Governance Enforcement | Governance Layer | COMPLETED | 359.7 |  |
| #4 | Native MCP vs OpenLakehouse Agent Coupling | Architecture | COMPLETED | 3.1 |  |
| #5 | Platform Extension Property Validation | Architecture | COMPLETED | 35.7 |  |


**Unit Tests:** 89 passed, 4 warnings in 3.13s

## Key Quantitative Findings

| Metric | Value |
|---|---|
| Platforms unified under CLM | 2 (Databricks, AWS) |
| MCP tools (agent-facing) | 5 (unchanged across platforms) |
| Metadata Conformance Rate | 100% (8/8 operations across both platforms) |
| Governance Conformance Rate | 100% (8/8 scenarios, 5 reason codes verified) |
| Authorization reason codes | 5 (structured, machine-readable) |
| Components changed to add new platform | 4 (1 new file, 3 minor edits) |
| Agent code changes to add new platform | **0** |
| Platform branches eliminated vs native multi-MCP | 2 → 0 |
| MCP endpoints vs native multi-MCP | 2 → 1 |

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
- `output/evaluations/overall_findings.md`
- `output/evaluations/summary.json`
- `output/evaluations/summary.md`

## Limitations

- Databricks query pagination is not resumable in v1 (next_page_token=None for Databricks)
- assert_read_only is a denylist/allowlist heuristic, not a full SQL parser
- AWS Lake Formation is rely-and-surface — OpenLakehouse does not proactively introspect LF grants
- SnowflakeAdapter in Experiment 5 is an architectural validation stub — not a production implementation
- Execution time measurements include network latency and warehouse cold-start overhead
- Scalar row value type normalization is out of scope for CLM v1
