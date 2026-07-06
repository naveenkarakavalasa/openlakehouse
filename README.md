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
| --- | --- | --- |
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
| --- | --- | --- |
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
| --- | --- | --- |
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

## Running

### Step 1 — Configure

```bash
cp config/config.example.yaml config/config.yaml
cp config/policy.example.yaml config/policy.yaml
```

Edit `config/config.yaml` with your platform details. Edit `policy.yaml` to map your agent identity to a role.

### Step 2 — Set environment variables

**Required for all adapters:**

| Variable | Purpose |
| --- | --- |
| `OPENLAKEHOUSE_IDENTITY` | Agent identity — must match an entry in `policy.yaml` |
| `OPENLAKEHOUSE_CONFIG` | Absolute path to your `config.yaml` |

**Databricks** — set these fields in `config.yaml`:

| Field | Value |
| --- | --- |
| `host` | Your Databricks workspace URL, e.g. `https://my-workspace.cloud.databricks.com` |
| `warehouse_http_path` | HTTP path of your SQL Warehouse, e.g. `/sql/1.0/warehouses/abc123` |
| `token_env` | Name of the environment variable that will hold your PAT, e.g. `DATABRICKS_PROD_TOKEN` |

**AWS** — set these fields in `config.yaml`:

| Field | Value |
| --- | --- |
| `region` | AWS region, e.g. `us-east-1` |
| `catalog_name` | Glue Data Catalog name, e.g. `AwsDataCatalog` |
| `athena_output_location` | S3 path for Athena query results, e.g. `s3://my-bucket/athena/` |

AWS credentials are not stored in `config.yaml` — use `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, a named profile (`AWS_PROFILE`), or an instance/container role.

**Collect the following values then set them using the commands below:**

| Variable | What to collect |
| --- | --- |
| `OPENLAKEHOUSE_IDENTITY` | The agent identity name you defined in `policy.yaml` |
| `OPENLAKEHOUSE_CONFIG` | Full path to your `config.yaml` |
| `DATABRICKS_PROD_TOKEN` | Databricks personal access token |
| `AWS_ACCESS_KEY_ID` | AWS access key ID |
| `AWS_SECRET_ACCESS_KEY` | AWS secret access key |

**Linux / macOS:**
```bash
export OPENLAKEHOUSE_IDENTITY=my-agent
export OPENLAKEHOUSE_CONFIG=/abs/path/to/config/config.yaml
export DATABRICKS_PROD_TOKEN=dapi...
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

**Windows:**
```cmd
set OPENLAKEHOUSE_IDENTITY=my-agent
set OPENLAKEHOUSE_CONFIG=C:\path\to\config\config.yaml
set DATABRICKS_PROD_TOKEN=dapi...
set AWS_ACCESS_KEY_ID=...
set AWS_SECRET_ACCESS_KEY=...
```

### Step 3 — Verify the server starts

Run the MCP Inspector to browse available tools interactively (requires Node.js):

```bash
npx @modelcontextprotocol/inspector openlakehouse
```

Or run the canonical interface demo to verify live data access (Snowflake stub runs without credentials; Databricks and AWS require Steps 1–2 above):

```bash
python experiments/canonical_interface_demo.py
```

### Step 4 — Connect OpenLakehouse to an agent

OpenLakehouse runs as a stdio MCP server. Any MCP-compatible agent framework accepts an `mcpServers` configuration block to spawn and connect to it:

```json
{
  "mcpServers": {
    "openlakehouse": {
      "command": "/abs/path/to/.venv/bin/openlakehouse",
      "env": {
        "OPENLAKEHOUSE_IDENTITY": "my-agent",
        "OPENLAKEHOUSE_CONFIG": "/abs/path/to/config/config.yaml",
        "DATABRICKS_PROD_TOKEN": "dapi...",
        "AWS_ACCESS_KEY_ID": "...",
        "AWS_SECRET_ACCESS_KEY": "..."
      }
    }
  }
}
```

Pass this configuration to your agent framework's MCP client initialisation. Refer to your framework's documentation for where this block is placed (e.g. Claude Desktop `claude_desktop_config.json`, Claude Code `claude mcp add`, or equivalent).

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
  version = {0.1.0},
  doi     = {10.5281/zenodo.21226569},
  url     = {https://doi.org/10.5281/zenodo.21226569}
}
```

## License

Apache-2.0. See [LICENSE](LICENSE).
