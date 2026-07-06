---
title: 'OpenLakehouse: A Canonical Interoperability Layer for AI Agent Access to Multi-Platform Lakehouse Data'
tags:
  - Python
  - artificial intelligence
  - data engineering
  - Model Context Protocol
  - lakehouse
  - data virtualization
  - access control
authors:
  - name: Naveen Karakavalasa
    orcid: 0009-0000-4697-9101
    affiliation: 1
  - name: Santosh Kotagiri
    orcid: 0009-0000-0205-1053
    affiliation: 2
affiliations:
  - name: Tokio Marine North America Services
    index: 1
  - name: Southwest Airlines
    index: 2
date: 2026-07-06
bibliography: paper.bib
---

# Summary

**OpenLakehouse is an open-source Python reference implementation of the Canonical
Lakehouse Model (CLM)**, an architectural pattern for giving AI agents uniform,
governed access to data across heterogeneous lakehouse platforms. Existing approaches
require agents to handle each platform's API, namespace model, and permission system
directly — coupling agent code to vendor-specific details that change independently.
The CLM addresses this by defining three canonical domains — metadata, query results,
and authorization decisions — into which any platform's native responses are
translated before reaching the agent.

OpenLakehouse exposes these canonical models through a Model Context Protocol (MCP)
server [@anthropic2024mcp] that translates platform-native responses into CLM data
structures implemented as Pydantic [@pydantic2024] models. AI agents invoke the same
MCP tools and receive the same canonical response structures regardless of the
underlying lakehouse platform.

Version 1 ships with adapters for Databricks (Unity Catalog and SQL Warehouse)
[@databricks2023] and AWS (Glue Data Catalog and Athena) [@awsglue2017]. A documented
`LakehouseAdapter` interface allows new platforms to be integrated without modifying
the MCP server, CLM models, or agent code.

# Statement of Need

Enterprise AI agents increasingly query data distributed across heterogeneous
lakehouse platforms [@armbrust2021lakehouse]. Each platform exposes a different API
surface: Databricks Unity Catalog uses a 3-level namespace and a synchronous DB-API
cursor; AWS Glue and Athena use a flat database namespace and an asynchronous
start-poll-fetch model; Snowflake, Google BigQuery, and Apache Spark
[@zaharia2016spark] each add further variations.

Connecting an agent to multiple platforms directly requires per-platform response
parsers, platform-specific branching on every tool call, and separate permission
models. This coupling grows linearly: each additional platform adds an MCP endpoint,
a response parser, and a governance configuration, with changes required in both
server and agent code.

Unlike deploying one MCP server per platform, OpenLakehouse presents a single
canonical interface that eliminates platform-specific parsing and governance logic
from AI agents. Platform-specific logic is encapsulated in adapter classes, so agents
always receive the same canonical response types — `CanonicalCatalog`,
`CanonicalSchema`, `CanonicalTable`, `CanonicalTableSchema`, and
`CanonicalQueryResult` — regardless of the underlying platform. Adding a new platform
requires no changes to the agent integration code.

Existing platform-specific MCP servers expose vendor-native APIs, while OpenLakehouse
provides a single canonical interface with centralized policy enforcement across
heterogeneous lakehouse platforms. The intended users are data engineers and AI
practitioners building agents over multi-vendor data estates. The CLM pattern also supports research workflows in
which AI agents must access and correlate data distributed across institutional
lakehouse deployments — a pattern common in computational science, bioinformatics,
and data-intensive social science research.

# Features

- **Canonical Lakehouse Model.** Metadata, query results, and authorization decisions
  are normalized into strongly typed Pydantic v2 models. Agents consume a consistent
  response schema regardless of which platform serves the data.

- **Unified MCP interface.** Five platform-independent tools — `list_catalogs`,
  `list_schemas`, `list_tables`, `describe_table`, and `run_query` — cover the full
  data discovery and query workflow. Tool signatures and response shapes are stable
  across platform changes.

- **Supported platforms.** Version 1 ships production adapters for Databricks (Unity
  Catalog + SQL Warehouse) and AWS (Glue + Athena). A Snowflake stub demonstrates the
  extension contract.

- **Governance.** A built-in policy engine enforces read-only, role-based access
  control with default-deny semantics. Policy is evaluated against a canonical
  resource scope before any adapter call, so governance cannot be bypassed.
  Authorization decisions carry structured reason codes for auditability.

- **Extensibility.** A new platform requires one adapter class implementing
  `LakehouseAdapter` and minor configuration edits — no changes to MCP tools,
  canonical models, or agent code.

## Canonical Lakehouse Model

The CLM covers three domains:

- **Metadata** — catalogs, schemas, and tables are normalized into `CanonicalCatalog`,
  `CanonicalSchema`, and `CanonicalTable` objects, regardless of the platform's
  namespace hierarchy.

- **Query Results** — output is wrapped in `CanonicalQueryResult`, carrying column
  definitions, typed rows, pagination metadata, and execution context.

- **Authorization** — decisions are returned as `CanonicalAuthorizationDecision`
  objects with structured reason codes, decoupling policy from platform permission
  systems.

Each adapter translates platform-native responses into canonical models via stateless
mapper functions. Agents never receive raw platform output.

| Platform   | Native Namespace        | Canonical Model   |
|------------|-------------------------|-------------------|
| Databricks | catalog.schema.table    | `CanonicalTable`  |
| AWS Glue   | database.table          | `CanonicalTable`  |
| Snowflake  | schema.table            | `CanonicalTable`  |

# Implementation

![OpenLakehouse architecture. AI agents communicate through a single MCP interface
backed by the CLM. Platform adapters translate native metadata and query results into
canonical models, while policy evaluation occurs before adapter invocation to enforce
consistent governance across all supported
platforms.](Figure1_clm_architecture.png)

OpenLakehouse is implemented across five packages — `core`, `adapters`, `policy`,
`identity`, and `server` — wired together via FastMCP [@fastmcp2024]. The key design
invariant is that the policy engine evaluates every request against a canonical
resource scope before any adapter method is called, ensuring governance cannot be
bypassed regardless of which platform is targeted.

# Demonstration

The `experiments/canonical_interface_demo.py` script issues the same `run_query` MCP
tool invocation against Databricks, AWS Athena, and a Snowflake stub, then compares
the resulting `CanonicalQueryResult` objects. The invocation is identical for every
platform:

```python
raw    = adapter.execute_query("SELECT 1 AS n", catalog=catalog, schema=schema)
result = query_result_to_canonical(raw, adapter.name, adapter.platform)
# result: CanonicalQueryResult — same four-field envelope for all platforms
```

Table 1 shows the output. The first five fields are structurally identical across
platforms; the final two carry expected per-platform values within the same canonical
envelope.

| Field                    | Databricks (live) | AWS Athena (live) | Snowflake (stub) |
|--------------------------|:-----------------:|:-----------------:|:----------------:|
| `columns[0].name`        | `"n"`             | `"n"`             | `"n"`            |
| `columns[0].data_type`   | `INTEGER`         | `INTEGER`         | `INTEGER`        |
| `rows[0]`                | `[1]`             | `["1"]`           | `[1]`            |
| `pagination.row_count`   | `1`               | `1`               | `1`              |
| `pagination.truncated`   | `False`           | `False`           | `False`          |
| `execution.platform`     | `"databricks"`    | `"aws"`           | `"snowflake"`    |
| `execution.query_id`     | `null`            | UUID              | `null`           |

: `query_id=null` for Databricks reflects a v1 connector limitation; the field is
present in the schema. Athena returns scalar values as strings (`"1"` rather than
`1`); coercion is outside the CLM v1 scope.

The Snowflake stub was created without modifying any core module, confirming that the
adapter interface supports extension without affecting existing behavior.

# Testing and Validation

The package includes 90 unit tests requiring no live cloud credentials. AWS tests run
against moto [@moto2024], an in-memory Glue/Athena mock; Databricks tests use
`pytest-mock` to patch `WorkspaceClient` and `databricks.sql.connect`. The suite
`tests/unit/test_tools.py` verifies the policy-before-adapter invariant: for each
denied scenario, a mock adapter asserts none of its methods are called.

Five validation experiments in `evaluation/` cover live Databricks and AWS
environments: metadata conformance (100%, 8/8 operations), query result shape
conformance (100%, 2/2 platforms), governance enforcement (100%, 8 authorization
scenarios), agent coupling reduction (2→1 endpoints, 2→0 platform branches in agent
code), and adapter extension (verified via the Snowflake stub).

# Future Work

Planned adapters include Snowflake, Google BigQuery, Azure Fabric, and Apache Spark.
Planned features include semantic metadata discovery, lineage-aware context retrieval,
integration with enterprise identity providers (Azure Active Directory, Okta), and
fine-grained column-level access control with audit logging.

# Acknowledgements

The authors thank the developers and maintainers of FastMCP, Pydantic, moto, and the
Model Context Protocol ecosystem for the foundational libraries that made this work
possible.

# AI Tool Usage

Claude (Anthropic) was used as a coding assistant during software development,
assisting with code generation and test writing. All research contributions, design
decisions, architectural choices, and evaluation results are the authors' own.

# References
