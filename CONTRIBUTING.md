# Contributing to OpenLakehouse

Thank you for your interest in contributing.

## Development Setup

```bash
git clone https://github.com/naveenkarakavalasa/openlakehouse.git
cd openlakehouse
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp config/config.example.yaml config/config.yaml
cp config/policy.example.yaml config/policy.yaml
```

## Running Tests

All unit tests run without live cloud credentials:

```bash
pytest
```

The AWS adapter tests use [moto](https://github.com/getmoto/moto) (in-memory
Glue/Athena). The Databricks adapter tests use `pytest-mock` to patch
`WorkspaceClient` and `databricks.sql.connect`.

## Adding a New Platform Adapter

1. Create `src/openlakehouse/adapters/<platform>_adapter.py` implementing
   the `LakehouseAdapter` ABC from `src/openlakehouse/core/adapter.py`.
   All five abstract methods must be implemented:
   `list_catalogs`, `list_schemas`, `list_tables`, `describe_table`, `execute_query`.

2. Add a `<Platform>AdapterConfig` Pydantic model to
   `src/openlakehouse/config/models.py` and extend the `AdapterConfig`
   discriminated union.

3. Add an `elif` branch to `src/openlakehouse/adapters/registry.py` mapping
   the new config type to the new adapter class.

4. Add an adapter block to `config/config.yaml` (gitignored locally; update
   `config/config.example.yaml` for documentation).

5. Add tests in `tests/unit/test_<platform>_adapter.py`.

The MCP tools, canonical models, and policy engine require **no changes**.
See `experiments/canonical_interface_demo.py` for a worked Snowflake stub
that demonstrates the full extension pattern.

## Code Style

- Python 3.11+, type-annotated throughout.
- Keep `core/` free of boto3/databricks-sdk imports.
- Every MCP tool must call `policy_engine.authorize()` **before** any adapter
  method — see `tests/unit/test_tools.py` for the invariant tests.
- No comments unless the *why* is non-obvious.

## Submitting Changes

1. Fork the repository and create a branch from `master`.
2. Make your changes and ensure `pytest` passes.
3. Open a pull request describing what changed and why.

## Reporting Issues

Use [GitHub Issues](https://github.com/naveenkarakavalasa/openlakehouse/issues).
