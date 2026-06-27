"""Shared utilities for all evaluation experiments."""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = REPO_ROOT / "output" / "evaluations"

CANONICAL_CATALOG_FIELDS = {"adapter", "platform", "catalog", "native_catalog", "platform_metadata"}
CANONICAL_SCHEMA_FIELDS = {"adapter", "platform", "catalog", "schema", "native_schema", "platform_metadata"}
CANONICAL_TABLE_FIELDS = {"adapter", "platform", "catalog", "schema", "table", "table_type", "platform_metadata"}
CANONICAL_TABLE_SCHEMA_FIELDS = {"table", "columns", "partition_columns", "table_format", "properties"}
CANONICAL_QUERY_FIELDS = {"columns", "rows", "pagination", "execution"}
CANONICAL_PAGINATION_FIELDS = {"truncated", "next_page_token", "row_count"}
CANONICAL_EXECUTION_FIELDS = {"adapter", "platform", "execution_time_ms", "query_id", "native_metadata"}


def check_fields(obj: dict, required: set[str]) -> tuple[bool, list[str]]:
    missing = [f for f in required if f not in obj]
    return len(missing) == 0, missing


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"  saved {path.relative_to(REPO_ROOT)}")


def save_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  saved {path.relative_to(REPO_ROOT)}")


def save_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    print(f"  saved {path.relative_to(REPO_ROOT)}")


def md_table(rows: list[dict], columns: list[str] | None = None) -> str:
    if not rows:
        return "_No results._\n"
    cols = columns or list(rows[0].keys())
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines = [header, sep]
    for row in rows:
        cells = [str(row.get(c, "")) for c in cols]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def try_load_adapters(config_path: str | None = None) -> tuple[dict, dict[str, str]]:
    """Try to build all configured adapters. Returns (adapters, errors)."""
    from openlakehouse.adapters.registry import build_adapter
    from openlakehouse.config.loader import load_config

    cfg_path = config_path or os.environ.get(
        "OPENLAKEHOUSE_CONFIG",
        str(REPO_ROOT / "config" / "config.yaml"),
    )

    adapters: dict = {}
    errors: dict[str, str] = {}

    try:
        app_config = load_config(cfg_path)
    except Exception as exc:
        return {}, {"config": str(exc)}

    for name, cfg in app_config.adapters.items():
        try:
            adp = build_adapter(name, cfg)
            adapters[name] = adp
        except Exception as exc:
            errors[name] = str(exc)

    return adapters, errors


def try_load_policy(config_path: str | None = None):
    """Load the policy engine from config."""
    from openlakehouse.config.loader import load_config
    from openlakehouse.policy.engine import PolicyEngine
    from openlakehouse.policy.loader import load_policy

    cfg_path = config_path or os.environ.get(
        "OPENLAKEHOUSE_CONFIG",
        str(REPO_ROOT / "config" / "config.yaml"),
    )
    try:
        app_config = load_config(cfg_path)
        policy_path = REPO_ROOT / app_config.policy_path
        policy_doc = load_policy(str(policy_path))
        return PolicyEngine(policy_doc), None
    except Exception as exc:
        return None, str(exc)


def timed(fn, *args, **kwargs) -> tuple[Any, float, str | None]:
    """Call fn(*args, **kwargs), return (result, elapsed_ms, error_or_None)."""
    t0 = time.monotonic()
    try:
        result = fn(*args, **kwargs)
        return result, (time.monotonic() - t0) * 1000, None
    except Exception as exc:
        return None, (time.monotonic() - t0) * 1000, str(exc)
