# OpenLakehouse Research Architecture

## Agent Data Virtualization

OpenLakehouse implements **Agent Data Virtualization** — a semantic interoperability layer that exposes heterogeneous lakehouse platforms to AI agents through a single, governed interface. Agents discover and query data across any number of platforms without needing platform-specific knowledge, credentials, or SDK integrations.

```
AI Agent (Claude, GPT, any MCP client)
           │  Model Context Protocol (MCP / stdio)
           ▼
┌──────────────────────────────────────────────┐
│               MCP Server Layer               │
│  5 tools: list_catalogs · list_schemas       │
│           list_tables · describe_table       │
│           run_query                          │
└──────────────┬───────────────────────────────┘
               │  Canonical Governance Layer
               │  (authorize before every adapter call)
┌──────────────▼───────────────────────────────┐
│             Policy Engine                    │
│  default-deny · last-match-wins              │
│  CanonicalAuthorizationDecision output       │
└──────┬───────────────────────┬───────────────┘
       │ Canonical Mapper       │ Canonical Mapper
┌──────▼──────────┐    ┌───────▼──────────────┐
│ DatabricksAdapter│    │     AWSAdapter        │
│ (platform=       │    │  (platform="aws")     │
│  "databricks")   │    │                       │
│  databricks-sdk  │    │  boto3 Glue + Athena  │
│  SQL Warehouse   │    │  S3 result staging    │
└──────────────────┘    └───────────────────────┘
```

---

## Canonical Lakehouse Model

The **Canonical Lakehouse Model** defines three families of platform-agnostic types:

### 1. Canonical Metadata Model (`core/canonical/metadata.py`)

Unifies catalog/schema/table/column concepts across all platforms.

| Model | Fields | Purpose |
|---|---|---|
| `CanonicalCatalog` | adapter, platform, catalog, native_catalog, platform_metadata | Top-level namespace entry |
| `CanonicalSchema` | adapter, platform, catalog, schema, native_schema | Database/schema within a catalog |
| `CanonicalTable` | adapter, platform, catalog, schema, table, table_type, platform_metadata | Table or view |
| `CanonicalColumn` | name, data_type, raw_type, nullable, is_partition_key, ordinal_position | Column with normalized type |
| `CanonicalTableSchema` | table, columns, partition_columns, table_format, properties | Full table structure |
| `CanonicalDataType` | STRING, INTEGER, BIGINT, FLOAT, DOUBLE, BOOLEAN, DATE, TIMESTAMP, DECIMAL, BINARY, ARRAY, MAP, STRUCT, UNKNOWN | Normalized type vocabulary |
| `PlatformNamespaceMapping` | platform, catalog_concept, schema_concept, table_concept | Documents how each platform maps to the 3-level hierarchy |

**Platform namespace mappings:**

| Concept | Databricks | AWS |
|---|---|---|
| catalog | Unity Catalog (e.g. `sales`) | Glue Data Catalog (`AwsDataCatalog`) |
| schema | Schema (e.g. `orders`) | Glue Database (e.g. `analytics`) |
| table | Table / View | Glue Table |
| metadata API | `databricks-sdk` WorkspaceClient | `boto3` Glue client |
| query engine | SQL Warehouse | Athena + S3 |

### 2. Canonical Query Model (`core/canonical/query.py`)

Normalizes query execution across platforms with different execution models.

| Model | Fields | Purpose |
|---|---|---|
| `CanonicalQueryResult` | columns, rows, pagination, execution | Full query result |
| `CanonicalQueryColumn` | name, data_type, raw_type, nullable | Column with normalized data type |
| `CanonicalPagination` | truncated, next_page_token, row_count | Pagination state |
| `CanonicalExecutionMetadata` | query_id, adapter, platform, execution_time_ms, native_metadata | Execution provenance |

**Platform-specific query model differences (hidden behind canonical layer):**

| Aspect | Databricks | AWS Athena |
|---|---|---|
| Execution model | Synchronous (SQL Warehouse cursor) | Async (start → poll → fetch from S3) |
| `query_id` | `None` (v1 limitation) | Athena `QueryExecutionId` (UUID) |
| Pagination | `truncated=True`, `next_page_token=None` — not resumable | Real `NextToken` encoded as `<query_execution_id>:<token>` |
| Header row | No duplication | First page row[0] is header — stripped by adapter |
| Type names | SDK enum: `LONG`, `TIMESTAMP_NTZ` | Glue: `bigint`; Athena result: `integer`, `varchar` |

### 3. Canonical Governance Model (`core/canonical/governance.py`)

Formalizes the access-control policy semantics.

| Model | Purpose |
|---|---|
| `CanonicalResourceScope` | 4-segment address: `adapter/catalog/schema/table`, `*` wildcard per segment |
| `CanonicalPolicyRule` | One rule: `effect` (allow/deny) + `scope` |
| `CanonicalRole` | Named set of rules + `permissions` (BROWSE and/or QUERY) |
| `CanonicalPolicy` | Full policy document: identities → roles mapping |
| `CanonicalAuthorizationDecision` | Structured decision with `allowed`, `effect`, `reason`, `reason_code` |
| `CanonicalReasonCode` | `ALLOWED`, `DENIED_BY_RULE`, `DENIED_NO_MATCHING_RULE`, `DENIED_NO_ROLE`, `DENIED_NO_QUERY_PERMISSION` |

**Policy semantics:**

- **Default-deny**: no matching rule → `DENIED_NO_MATCHING_RULE`
- **Last-match-wins**: rules are evaluated in order; the last matched rule's effect wins
- **BROWSE vs QUERY separation**: `CanonicalPermission.BROWSE` covers list/describe; `QUERY` covers SQL execution
- **`authorize_with_decision()`**: returns a `CanonicalAuthorizationDecision` for introspection; **`authorize()`** raises `PermissionDeniedError` for tool-layer enforcement

---

## Policy-Before-Adapter Invariant

Every MCP tool calls `policy_engine.authorize()` **before** any adapter method. This is:

1. **Structurally enforced**: the tool code calls `authorize()` first, then `get_adapter()` — there is no code path that reaches the adapter without passing through the policy engine
2. **Tested by mock**: `test_tools.py` passes a `Mock(spec=LakehouseAdapter)` and asserts `.assert_not_called()` on adapter methods when policy denies — proves the adapter is never reached

```python
# Every tool follows this pattern (simplified):
ctx.policy_engine.authorize(identity, adapter=adapter, catalog=catalog, ...)  # raises if denied
result = ctx.get_adapter(adapter).list_schemas(catalog)                         # only reached if allowed
return [schema_to_canonical(s, adp.platform).model_dump() for s in visible]    # canonical output
```

---

## Read-Only Governed Access

`core/sql_guard.py::assert_read_only(sql)` enforces read-only SQL at the framework layer, independent of platform privileges:

- **Allowlist**: statement must start with `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, or `EXPLAIN`
- **Denylist**: statement must not contain `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `MERGE`, `GRANT`, `REVOKE` as a word

Both adapters call `assert_read_only(sql)` before executing any query. Platform-level read-only grants provide defense in depth.

---

## Unified Agent Governance

The combination of policy engine + SQL guard + canonical model creates a **Unified Agent Governance** layer:

| Governance control | Mechanism | Where enforced |
|---|---|---|
| Identity resolution | `OPENLAKEHOUSE_IDENTITY` env var | `identity/resolver.py` at process start |
| Resource access | `PolicyEngine.authorize()` | `server/tools.py` before every adapter call |
| Silent list filtering | `PolicyEngine.filter_*()` | `server/tools.py` for list_* tools |
| Read-only SQL | `assert_read_only()` | Both adapters before query execution |
| Platform denial | boto3 `AccessDeniedException` → `PermissionDeniedError` | AWS adapter |
| Clean error surfacing | `mcp_tool_errors` decorator | `server/tools.py` wrapping all tools |

---

## Adding a New Adapter (Extensibility)

To add a third platform (e.g. Snowflake):

1. **`src/openlakehouse/adapters/snowflake_adapter.py`** — implement `LakehouseAdapter` with `platform = "snowflake"`
2. **`src/openlakehouse/config/models.py`** — add `SnowflakeAdapterConfig(type="snowflake", ...)`
3. **`src/openlakehouse/adapters/registry.py`** — add `elif isinstance(cfg, SnowflakeAdapterConfig)` branch
4. **`tests/unit/test_snowflake_adapter.py`** — unit tests with mocked Snowflake client

No changes to MCP tools, canonical models, policy engine, or agent-facing interface. The agent calling `list_catalogs` the next day simply sees additional catalogs tagged with `platform="snowflake"`.

---

## Evaluation Scripts (`evaluation/`)

| Script | Purpose | Output |
|---|---|---|
| `complexity_metrics.py` | LOC, public method count, files required to add an adapter | JSON / CSV |
| `governance_matrix.py` | Allow/deny/filter scenarios, reason codes, adapter-not-called assertion | JSON / CSV |
| `semantic_consistency.py` | Compares canonical objects from both platforms, surfaces hidden differences | JSON |
| `performance_probe.py` | Latency per operation per adapter | CSV (adapter, platform, operation, latency_ms, row_count, success) |

**Run without live credentials:**
```bash
python -m evaluation.complexity_metrics
python -m evaluation.governance_matrix --csv
python -m evaluation.semantic_consistency
```

**Run with live credentials (performance_probe):**
```bash
OPENLAKEHOUSE_CONFIG=config/config.yaml \
DATABRICKS_PROD_TOKEN=dapi... \
AWS_ACCESS_KEY_ID=... \
python -m evaluation.performance_probe --csv
```

---

## Running Tests

```bash
.venv/bin/python -m pytest tests/unit/           # all unit tests, no credentials needed
.venv/bin/python -m pytest tests/unit/test_canonical_metadata.py   # canonical metadata
.venv/bin/python -m pytest tests/unit/test_canonical_query.py      # canonical query
.venv/bin/python -m pytest tests/unit/test_canonical_governance.py # governance model
.venv/bin/python -m pytest tests/unit/test_canonical_mapper.py     # mapper functions
.venv/bin/python -m pytest tests/unit/test_tools.py                # MCP tool layer + policy invariant
```
