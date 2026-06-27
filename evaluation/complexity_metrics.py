"""Integration Complexity Metrics

Measures the structural cost of adding a new lakehouse adapter to OpenLakehouse.
Outputs JSON/CSV suitable for paper tables.

Usage:
    python -m evaluation.complexity_metrics
    python -m evaluation.complexity_metrics --csv
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SRC_ROOT = REPO_ROOT / "src" / "openlakehouse"

ADAPTER_FILES = {
    "databricks": SRC_ROOT / "adapters" / "databricks_adapter.py",
    "aws": SRC_ROOT / "adapters" / "aws_adapter.py",
}

FILES_TOUCHED_TO_ADD_ADAPTER = [
    "src/openlakehouse/adapters/<platform>_adapter.py",
    "src/openlakehouse/adapters/registry.py",
    "src/openlakehouse/config/models.py",
    "tests/unit/test_<platform>_adapter.py",
]


def count_loc(path: Path) -> int:
    """Count non-empty, non-comment lines in a Python file."""
    lines = path.read_text().splitlines()
    return sum(
        1 for line in lines
        if line.strip() and not line.strip().startswith("#")
    )


def count_public_methods(path: Path) -> int:
    """Count public method definitions in a Python file."""
    tree = ast.parse(path.read_text())
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not item.name.startswith("_"):
                        count += 1
    return count


def count_abstract_methods() -> int:
    """Count abstract methods in the LakehouseAdapter ABC."""
    path = SRC_ROOT / "core" / "adapter.py"
    tree = ast.parse(path.read_text())
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "LakehouseAdapter":
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorators = [
                        (d.id if isinstance(d, ast.Name) else
                         d.attr if isinstance(d, ast.Attribute) else "")
                        for d in item.decorator_list
                    ]
                    if "abstractmethod" in decorators:
                        count += 1
    return count


def adapter_complexity_report() -> dict:
    """Generate the full integration complexity report."""
    adapter_metrics = []
    for platform, path in ADAPTER_FILES.items():
        if not path.exists():
            continue
        adapter_metrics.append({
            "platform": platform,
            "file": str(path.relative_to(REPO_ROOT)),
            "loc": count_loc(path),
            "public_methods": count_public_methods(path),
        })

    return {
        "abstract_interface_methods": count_abstract_methods(),
        "files_required_to_add_adapter": len(FILES_TOUCHED_TO_ADD_ADAPTER),
        "file_list_to_add_adapter": FILES_TOUCHED_TO_ADD_ADAPTER,
        "adapters": adapter_metrics,
    }


def main() -> None:
    report = adapter_complexity_report()
    if "--csv" in sys.argv:
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=["platform", "file", "loc", "public_methods"],
        )
        writer.writeheader()
        for row in report["adapters"]:
            writer.writerow(row)
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
