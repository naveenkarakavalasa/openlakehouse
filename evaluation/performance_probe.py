"""Performance Probe

Measures latency for each MCP tool operation against live adapters.
Outputs CSV rows suitable for paper performance tables.

Requires live credentials. Pass adapter instances built from a real config.

Usage (from project root with env vars set):
    python -m evaluation.performance_probe
"""
from __future__ import annotations

import csv
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Any

from openlakehouse.core.adapter import LakehouseAdapter


@dataclass
class ProbeResult:
    adapter: str
    platform: str
    operation: str
    latency_ms: float
    row_count: int | None
    success: bool
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _probe(adapter: LakehouseAdapter, operation: str, fn, *args, **kwargs) -> ProbeResult:
    t0 = time.monotonic()
    try:
        result = fn(*args, **kwargs)
        elapsed = (time.monotonic() - t0) * 1000
        row_count = None
        if hasattr(result, "row_count"):
            row_count = result.row_count
        elif isinstance(result, list):
            row_count = len(result)
        return ProbeResult(
            adapter=adapter.name,
            platform=adapter.platform,
            operation=operation,
            latency_ms=round(elapsed, 2),
            row_count=row_count,
            success=True,
        )
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        return ProbeResult(
            adapter=adapter.name,
            platform=adapter.platform,
            operation=operation,
            latency_ms=round(elapsed, 2),
            row_count=None,
            success=False,
            error=str(exc),
        )


def probe_adapter(
    adapter: LakehouseAdapter,
    catalog: str,
    schema: str,
    table: str,
    query: str = "SELECT 1",
) -> list[ProbeResult]:
    """Run all five operations against one adapter and return timing results."""
    results = []

    results.append(_probe(adapter, "list_catalogs", adapter.list_catalogs))

    catalogs = adapter.list_catalogs()
    if catalogs:
        results.append(_probe(adapter, "list_schemas", adapter.list_schemas, catalog))

    results.append(_probe(adapter, "list_tables", adapter.list_tables, catalog, schema))
    results.append(_probe(adapter, "describe_table", adapter.describe_table, catalog, schema, table))
    results.append(_probe(adapter, "run_query", adapter.execute_query, query,
                          catalog=catalog, schema=schema, max_rows=100))

    return results


def run_probes(adapters: list[tuple[LakehouseAdapter, str, str, str, str]]) -> list[ProbeResult]:
    """Run probes across multiple adapters.

    Each tuple: (adapter, catalog, schema, table, probe_query)
    """
    all_results = []
    for adapter, catalog, schema, table, query in adapters:
        all_results.extend(probe_adapter(adapter, catalog, schema, table, query))
    return all_results


def results_to_csv(results: list[ProbeResult], file=None) -> None:
    out = file or sys.stdout
    writer = csv.DictWriter(
        out,
        fieldnames=["adapter", "platform", "operation", "latency_ms", "row_count", "success", "error"],
    )
    writer.writeheader()
    for r in results:
        d = asdict(r)
        d.pop("extra", None)
        writer.writerow(d)


def main() -> None:
    """Example: load config and run probes against configured adapters."""
    import os
    config_path = os.environ.get("OPENLAKEHOUSE_CONFIG", "config/config.yaml")

    try:
        from openlakehouse.config.loader import load_config
        from openlakehouse.adapters.registry import build_adapter

        app_config = load_config(config_path)
        adapters_to_probe = []
        for name, cfg in app_config.adapters.items():
            try:
                adp = build_adapter(name, cfg)
                # Use first available catalog/schema/table — override via CLI args in practice
                adapters_to_probe.append((adp, "*", "*", "*", "SELECT 1"))
            except Exception as exc:
                print(f"# Skipping {name}: {exc}", file=sys.stderr)

        results = run_probes(adapters_to_probe)

        if "--csv" in sys.argv:
            results_to_csv(results)
        else:
            print(json.dumps([asdict(r) for r in results], indent=2))

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Set OPENLAKEHOUSE_CONFIG and credentials, then retry.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
