# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-06

### Added

- **Canonical Lakehouse Model (CLM)** — three-layer abstraction (Metadata,
  Query, Governance) normalising platform-native responses into consistent
  Pydantic v2 models (`CanonicalCatalog`, `CanonicalSchema`, `CanonicalTable`,
  `CanonicalTableSchema`, `CanonicalQueryResult`, `CanonicalAuthorizationDecision`).
- **MCP server** — five platform-independent tools (`list_catalogs`,
  `list_schemas`, `list_tables`, `describe_table`, `run_query`) via FastMCP
  on stdio transport.
- **Databricks adapter** — Unity Catalog metadata via `databricks-sdk` and
  query execution via `databricks-sql-connector` against a SQL Warehouse.
- **AWS adapter** — Glue Data Catalog metadata and Athena query execution
  via `boto3`, with real resumable pagination via `NextToken`.
- **Policy engine** — default-deny, last-match-wins role-based access control.
  Every MCP tool evaluates policy before any adapter call.
- **Identity resolver** — process-level identity from `OPENLAKEHOUSE_IDENTITY`
  environment variable, matching MCP stdio transport semantics.
- **Read-only SQL guard** — `assert_read_only()` rejects DDL/DML before
  queries reach the adapter.
- **90 unit tests** — credential-free; AWS via moto, Databricks via pytest-mock.
- **CLI entry point** — `openlakehouse` command installed by pip.
- **`LakehouseAdapter` extension contract** — new platforms require one new
  adapter file and minor config edits; no changes to MCP tools or canonical models.

### Known Limitations

- Databricks query pagination is not resumable across requests (SQL connector
  limitation); use `LIMIT`/`WHERE` to narrow result sets.
- `assert_read_only` is a keyword heuristic, not a full SQL parser.
- AWS Lake Formation grants are surfaced but not proactively introspected.
- No MCP resources in v1 — all operations use tools.
