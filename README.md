# OpenLakehouse

**OpenLakehouse is an open-source Python reference implementation of the
Canonical Lakehouse Model (CLM)** — an architectural pattern for giving AI
agents uniform, governed access to data across heterogeneous lakehouse
platforms.

Enterprise AI agents increasingly query data distributed across platforms with
incompatible APIs: Databricks Unity Catalog uses a 3-level namespace and a
synchronous DB-API cursor; AWS Glue and Athena use a flat database namespace
and an asynchronous start-poll-fetch model. Connecting an agent to multiple
platforms directly requires per-platform response parsers, platform-specific
branching on every tool call, and separate permission models.

OpenLakehouse eliminates this coupling by translating platform-native responses
into **canonical models** — strongly typed Pydantic v2 structures — before they
reach the agent. Agents always receive the same `CanonicalCatalog`,
`CanonicalSchema`, `CanonicalTable`, `CanonicalTableSchema`, and
`CanonicalQueryResult` shapes regardless of the underlying platform. The
software exposes these through a **Model Context Protocol (MCP) server** so
any MCP-aware agent (Claude, GPT, or any MCP client) can discover and query
data with the same five tools across all configured platforms.

Version 1 ships production adapters for **Databricks** (Unity Catalog + SQL
Warehouse) and **AWS** (Glue Data Catalog + Athena). A documented
`LakehouseAdapter` interface allows new platforms to be integrated without
modifying the MCP server, canonical models, or agent code.

## Canonical Lakehouse Model

The CLM defines three layers of platform-agnostic abstractions:

| Layer | Canonical Types | What it normalises |
|---|---|---|
| **Metadata** | `CanonicalCatalog`, `CanonicalSchema`, `CanonicalTable`, `CanonicalTableSchema` | Namespace hierarchies, column types, table formats |
| **Query** | `CanonicalQueryResult`, `CanonicalQueryColumn`, `CanonicalPagination`, `CanonicalExecutionMetadata` | Synchronous vs. async execution, result pagination, type vocabularies |
| **Governance** | `CanonicalAuthorizationDecision`, `CanonicalReasonCode` | Platform-independent access control with structured reason codes |

Each adapter translates platform-native responses into canonical models via
stateless mapper functions. Agents never receive raw platform output. Adding a
new platform requires one new adapter class — no changes to tools, canonical
models, or agent code.

## Architecture

```
src/openlakehouse/
├── core/
│   ├── adapter.py      # LakehouseAdapter ABC — the extension contract
│   ├── models.py       # Internal Pydantic models (adapter return types)
│   ├── canonical/      # CLM: metadata, query, governance models + mapper
│   ├── sql_guard.py    # assert_read_only() — rejects DDL/DML
│   └── errors.py       # OpenLakehouseError hierarchy
├── adapters/           # DatabricksAdapter, AWSAdapter, registry factory
├── policy/             # PolicyEngine: default-deny, last-match-wins rules
├── identity/           # IdentityResolver: process-level agent identity
├── config/             # Pydantic config models + YAML loaders
└── server/             # FastMCP wiring: 5 tools, ServerContext, build_server()
```

`core` has no dependency on boto3 or databricks-sdk. `policy` and `identity`
are isolated from `adapters`. `server` is the only wiring layer — and is where
every tool calls the policy engine *before* touching an adapter, never after.

## MCP Tools

| Tool | Input | Output |
|---|---|---|
| `list_catalogs` | `{}` | Canonical catalogs visible to the current identity, across all adapters |
| `list_schemas` | `{adapter, catalog}` | Canonical schemas within a catalog |
| `list_tables` | `{adapter, catalog, schema}` | Canonical tables/views within a schema |
| `describe_table` | `{adapter, catalog, schema, table}` | Full canonical column/type/partition schema |
| `run_query` | `{adapter, sql, catalog?, schema?, max_rows?, page_token?}` | One page of canonical query results |

`run_query` only accepts read-only statements (`SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN`).

## Installation

```bash
pip install git+https://github.com/naveenkarakavalasa/openlakehouse.git
```

Or clone and install in development mode:

```bash
git clone https://github.com/naveenkarakavalasa/openlakehouse.git
cd openlakehouse
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config/config.example.yaml config/config.yaml
cp config/policy.example.yaml config/policy.yaml
# edit config.yaml and policy.yaml for your environment
```

Requires Python 3.11+. Secrets are never stored in `config.yaml` — Databricks
PATs are referenced by env var name (`token_env`), and AWS credentials defer
to the standard boto3 credential chain (profile / env vars / instance role).

## Running

```bash
OPENLAKEHOUSE_IDENTITY=claude-desktop-analyst \
OPENLAKEHOUSE_CONFIG=config/config.yaml \
DATABRICKS_PROD_TOKEN=dapi... \
AWS_PROFILE=openlakehouse-readonly \
openlakehouse
```

### Claude Desktop / Claude Code MCP config

```json
{
  "mcpServers": {
    "openlakehouse": {
      "command": "/abs/path/to/.venv/bin/openlakehouse",
      "env": {
        "OPENLAKEHOUSE_IDENTITY": "claude-desktop-analyst",
        "OPENLAKEHOUSE_CONFIG": "/abs/path/to/config/config.yaml",
        "DATABRICKS_PROD_TOKEN": "dapi...",
        "AWS_PROFILE": "openlakehouse-readonly"
      }
    }
  }
}
```

### Smoke test without a full agent client

```bash
npx @modelcontextprotocol/inspector openlakehouse
```

## Identity and Access Control

MCP's stdio transport has no per-request auth channel — one server process is
launched per MCP client config entry. Identity is resolved **once at process
startup** from the required `OPENLAKEHOUSE_IDENTITY` env var. Every tool call
within that process uses the same identity for policy purposes.

`policy.yaml` maps identities to roles, and roles to ordered allow/deny rules
matched against `adapter`/`catalog`/`schema`/`table` (exact match or `"*"`
wildcard per segment). Rules use **last-match-wins** evaluation and access is
**default-deny** — no matching rule means denied. `list_*` tools silently
filter out unauthorized items; `describe_table` and `run_query` return an
explicit `PermissionDeniedError` when the named resource is denied.

## Canonical Interface Demo

`experiments/canonical_interface_demo.py` issues the same query against
Databricks, AWS Athena, and a Snowflake stub, then compares the
`CanonicalQueryResult` objects side by side:

```bash
# Snowflake stub only (no credentials required):
python experiments/canonical_interface_demo.py

# With Databricks + AWS credentials:
set -a && source .env && set +a
python experiments/canonical_interface_demo.py
```

The demo confirms the **Zero Agent Modification Property**: adding the
Snowflake adapter required no changes to MCP tools, canonical models, or the
policy engine.

## Known v1 Limitations

- **Databricks query pagination is not resumable.** The SQL connector does not
  expose a server-side cursor across requests — `run_query` returns
  `truncated=True`, `next_page_token=None`. Narrow with `LIMIT`/`WHERE`
  instead. AWS/Athena supports real resumable pagination via `NextToken`.
- **`assert_read_only` is a keyword heuristic, not a SQL parser.** A CTE
  named `with updated as (...)` could false-positive on the forbidden-keyword
  check. Run adapters with read-only platform grants as defense in depth.
- **AWS Lake Formation is "rely-and-surface," not introspected.** If LF denies
  the underlying IAM principal, the AWS adapter maps the resulting
  `AccessDeniedException` to `PermissionDeniedError`. LF grants are not
  proactively read or used to filter listings.
- **No MCP resources in v1** — all operations use tools.

## Testing

```bash
pytest
```

90 unit tests require no live cloud credentials: the AWS adapter is tested
against [moto](https://github.com/getmoto/moto) (in-memory Glue/Athena) and
the Databricks adapter uses `pytest-mock` to patch `WorkspaceClient` and
`databricks.sql.connect`. `tests/unit/test_tools.py` specifically verifies the
policy-before-adapter invariant: for each denied scenario, a mock adapter
asserts none of its methods were called.

## Evaluation Suite

Five experiments in `evaluation/` validate the CLM's architectural properties.
Experiments 3–5 run without live credentials:

| Experiment | What it validates | Needs credentials |
|---|---|---|
| 1 — Metadata Normalization | Databricks + AWS produce identical canonical metadata shapes | Yes |
| 2 — Query Normalization | Both platforms return identical `CanonicalQueryResult` envelope | Yes |
| 3 — Governance Enforcement | Default-deny, reason codes, policy-before-adapter invariant | No |
| 4 — Agent Coupling | Static comparison: native multi-MCP vs. CLM approach | No |
| 5 — Platform Extension | Zero Agent Modification Property via Snowflake stub | No |

```bash
# Run all (with live credentials):
set -a && source .env && set +a
python -m evaluation.run_all_experiments

# Run without live credentials (experiments 3–5 only):
python -m evaluation.run_all_experiments --skip-live
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and feature requests go to
[GitHub Issues](https://github.com/naveenkarakavalasa/openlakehouse/issues).

## Citation

If you use OpenLakehouse in your research, please cite:

```bibtex
@software{karakavalasa2026openlakehouse,
  author  = {Karakavalasa, Naveen and Kotagiri, Santosh},
  title   = {OpenLakehouse: A Canonical Interoperability Layer for AI Agent Access to Multi-Platform Lakehouse Data},
  year    = {2026},
  url     = {https://github.com/naveenkarakavalasa/openlakehouse},
  version = {0.1.0}
}
```

## License

Apache-2.0. See [LICENSE](LICENSE).
