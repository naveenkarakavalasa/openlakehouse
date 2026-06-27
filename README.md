# OpenLakehouse

An MCP server that gives AI agents unified, governed read access to data spread across
proprietary lakehouse platforms. v1 supports **Databricks** (Unity Catalog + SQL Warehouse)
and **AWS** (Glue Data Catalog + Athena). Agents connect once over MCP and use the same five
tools regardless of which platform a given catalog actually lives on.

## Why

Lakehouse data is fragmented across platforms with different APIs, catalogs, and SQL dialects.
OpenLakehouse abstracts that behind a single `LakehouseAdapter` interface and exposes it to
agents as MCP tools, with a real access-control layer in front so an agent only sees data it's
authorized for.

## Architecture

```
src/openlakehouse/
├── core/       # platform-agnostic models, the LakehouseAdapter interface, the read-only SQL guard
├── adapters/   # DatabricksAdapter, AWSAdapter, and the config -> adapter factory
├── policy/     # PolicyEngine: default-deny, last-match-wins allow/deny rules
├── identity/   # resolves the agent identity for this server process
├── config/     # pydantic models + YAML loaders for config.yaml / policy.yaml
└── server/     # FastMCP wiring: the 5 tools, ServerContext, build_server()
```

`core` has no dependency on boto3/databricks-sdk. `policy` and `identity` don't depend on
adapters. `server` is the only layer that wires everything together, and is where every tool
calls into the policy engine *before* touching an adapter — never after.

## Tools exposed

| Tool | Input | Output |
|---|---|---|
| `list_catalogs` | `{}` | catalogs visible to the current identity, across all adapters |
| `list_schemas` | `{adapter, catalog}` | schemas (databases) in that catalog |
| `list_tables` | `{adapter, catalog, schema}` | tables/views in that schema |
| `describe_table` | `{adapter, catalog, schema, table}` | full column/type/partition metadata |
| `run_query` | `{adapter, sql, catalog?, schema?, max_rows?, page_token?}` | one page of query results |

`run_query` only accepts read-only statements (`SELECT`/`WITH`/`SHOW`/`DESCRIBE`/`EXPLAIN`).

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp config/config.example.yaml config/config.yaml
cp config/policy.example.yaml config/policy.yaml
# edit config.yaml/policy.yaml for your environment, then set credentials via env vars
```

Secrets are never stored in `config.yaml` — Databricks PATs are referenced by env var name
(`token_env`), and AWS credentials defer entirely to the standard boto3 credential chain
(profile / env vars / instance role / SSO).

## Running

```bash
OPENLAKEHOUSE_IDENTITY=claude-desktop-analyst \
OPENLAKEHOUSE_CONFIG=config/config.yaml \
DATABRICKS_PROD_TOKEN=dapi... \
AWS_PROFILE=openlakehouse-readonly \
.venv/bin/python -m openlakehouse
```

### Claude Desktop / Claude Code MCP config

```json
{
  "mcpServers": {
    "openlakehouse": {
      "command": "/abs/path/to/openlakehouse/.venv/bin/python",
      "args": ["-m", "openlakehouse"],
      "env": {
        "OPENLAKEHOUSE_IDENTITY": "claude-desktop-analyst",
        "OPENLAKEHOUSE_CONFIG": "/abs/path/to/openlakehouse/config/config.yaml",
        "DATABRICKS_PROD_TOKEN": "dapi...",
        "AWS_PROFILE": "openlakehouse-readonly"
      }
    }
  }
}
```

### Manual smoke test without a full agent client

```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m openlakehouse
```

## Identity and access control (v1 trust model)

MCP's stdio transport has no per-request auth channel, and in practice one server *process* is
launched per MCP client config entry. So v1 identity is resolved **once at process startup**
from the required `OPENLAKEHOUSE_IDENTITY` env var — every tool call within that process is the
same agent identity for policy purposes. Whoever controls the server's launch config controls
its identity, the same as any other locally-configured credential.

`policy.yaml` maps identities to roles, and roles to ordered allow/deny rules matched against
`adapter`/`catalog`/`schema`/`table` (exact match or `"*"` wildcard per segment). Rules are
evaluated in order with **last-match-wins**, and access is **default-deny** — no matching rule
means denied. `list_*` tools silently filter out items an identity can't see; `describe_table`
and `run_query` raise an explicit `PermissionDeniedError` when the named resource is denied.

## Known v1 limitations

- **Databricks query pagination isn't resumable.** The SQL connector doesn't expose a
  server-side cursor across requests, so a truncated Databricks `run_query` result has
  `next_page_token=None` — narrow with `LIMIT`/`WHERE` instead of paging. AWS/Athena *does*
  support real pagination via `NextToken`.
- **`assert_read_only` is a denylist/allowlist heuristic, not a SQL parser.** A CTE literally
  named e.g. `with updated as (...)` could in theory false-positive on the forbidden-keyword
  check. Run adapters with read-only platform grants as defense in depth.
- **AWS Lake Formation is "rely-and-surface," not introspected.** If Lake Formation denies the
  underlying IAM principal, the boto3 call itself fails with `AccessDeniedException`, which the
  AWS adapter maps to `PermissionDeniedError`. OpenLakehouse does not proactively read LF grants
  or filter listings based on them — combine LF with the OpenLakehouse policy layer for full
  coverage.
- **No MCP resources in v1**, only tools — every operation here needs runtime parameters or
  benefits from explicit tool-call semantics, which fits tools better than resources.

## Testing

```bash
.venv/bin/python -m pytest
```

Unit tests require no live cloud credentials: the policy engine and identity resolver are pure
Python, the AWS adapter is tested against `moto`'s in-memory Glue/Athena, and the Databricks
adapter is tested with `pytest-mock` patching `WorkspaceClient`/`databricks.sql.connect`. The
tool-layer tests (`tests/unit/test_tools.py`) specifically assert that a denied policy check
prevents the underlying adapter from ever being called — the core "governed access" invariant.

## Paper Evaluation Suite

Five experiments covering the Canonical Lakehouse Model (CLM) research contribution:

| Experiment | Description | Needs Live Credentials |
|---|---|---|
| 1 — Metadata Normalization | Verify Databricks + AWS return identical canonical metadata shapes | Yes |
| 2 — Query Normalization | Verify both platforms return identical CanonicalQueryResult | Yes |
| 3 — Governance Enforcement | Validate default-deny, reason codes, policy-before-adapter invariant | No |
| 4 — Agent Coupling | Static comparison: native MCP vs OpenLakehouse CLM | No |
| 5 — Platform Extension | Zero Agent Modification Property with SnowflakeAdapter stub | No |

**Run all experiments:**

```bash
# With live Databricks + AWS credentials
set -a && source .env && set +a
python -m evaluation.run_all_experiments

# Without live credentials (experiments 3–5 only)
python -m evaluation.run_all_experiments --skip-live
```

**Run individual experiments:**

```bash
python -m evaluation.experiment_1_metadata_normalization
python -m evaluation.experiment_2_query_normalization
python -m evaluation.experiment_3_governance_enforcement
python -m evaluation.experiment_4_agent_coupling
python -m evaluation.experiment_5_platform_extension
```

Output files are written to `output/evaluations/` (JSON, CSV, Markdown per experiment plus `summary.md`).
