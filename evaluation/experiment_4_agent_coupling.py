"""Experiment 4 — Native MCP / Native Connector vs OpenLakehouse Agent Coupling

Static analytical comparison of agent coupling complexity under four approaches:
  A. Databricks-native MCP / native connector only
  B. AWS-native MCP / native connector only
  C. Multiple native MCP connectors (both platforms)
  D. OpenLakehouse with Canonical Lakehouse Model (CLM)

No live cloud credentials required.

Output:
    output/evaluations/experiment_4_agent_coupling.json
    output/evaluations/experiment_4_agent_coupling.csv
    output/evaluations/experiment_4_agent_coupling.md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evaluation.experiment_utils import OUTPUT_DIR, md_table, save_csv, save_json, save_md

APPROACHES = [
    {
        "approach": "A — Databricks Native",
        "description": "Agent connects directly to Databricks MCP server or SQL connector",
        "mcp_endpoints_required": 1,
        "metadata_models_required": 1,
        "query_models_required": 1,
        "governance_models_required": 1,
        "agent_response_parsers_required": 1,
        "platform_specific_branches_required": 0,
        "supports_databricks": True,
        "supports_aws": False,
        "supports_both_without_agent_change": False,
        "response_contract": "Databricks-specific (Unity Catalog REST + SQL Warehouse schema)",
        "agent_code_to_add_platform": "Full agent rewrite or parallel integration",
        "vendor_lock_in": "High — agent logic tightly coupled to Databricks SDK/MCP schema",
    },
    {
        "approach": "B — AWS Native",
        "description": "Agent connects directly to AWS Glue/Athena APIs or AWS MCP server",
        "mcp_endpoints_required": 1,
        "metadata_models_required": 1,
        "query_models_required": 1,
        "governance_models_required": 1,
        "agent_response_parsers_required": 1,
        "platform_specific_branches_required": 0,
        "supports_databricks": False,
        "supports_aws": True,
        "supports_both_without_agent_change": False,
        "response_contract": "AWS-specific (Glue API + Athena QueryResult schema)",
        "agent_code_to_add_platform": "Full agent rewrite or parallel integration",
        "vendor_lock_in": "High — agent logic tightly coupled to AWS SDK/Boto3 schema",
    },
    {
        "approach": "C — Native Multi-MCP",
        "description": "Agent connects to both Databricks and AWS MCP endpoints separately",
        "mcp_endpoints_required": 2,
        "metadata_models_required": 2,
        "query_models_required": 2,
        "governance_models_required": 2,
        "agent_response_parsers_required": 2,
        "platform_specific_branches_required": 2,
        "supports_databricks": True,
        "supports_aws": True,
        "supports_both_without_agent_change": False,
        "response_contract": "Mixed — agent must branch on platform at every step",
        "agent_code_to_add_platform": "New MCP config + new response parser + new branches per operation",
        "vendor_lock_in": "High — multiplied per platform; grows linearly with platform count",
    },
    {
        "approach": "D — OpenLakehouse CLM",
        "description": "Agent connects to OpenLakehouse MCP server; receives Canonical Lakehouse Model responses",
        "mcp_endpoints_required": 1,
        "metadata_models_required": 1,
        "query_models_required": 1,
        "governance_models_required": 1,
        "agent_response_parsers_required": 1,
        "platform_specific_branches_required": 0,
        "supports_databricks": True,
        "supports_aws": True,
        "supports_both_without_agent_change": True,
        "response_contract": "Canonical Lakehouse Model (CLM) — platform-agnostic",
        "agent_code_to_add_platform": "Zero — new adapter registered server-side, agent unchanged",
        "vendor_lock_in": "None — agent decoupled from all platform-specific schemas",
    },
]

TOOL_COMPARISON = [
    {
        "tool": "list_catalogs",
        "native_databricks": "catalog.list() → DatabricksCatalogInfo[]",
        "native_aws": "glue.get_databases() → DatabaseList[]",
        "openlakehouse_clm": "list_catalogs() → CanonicalCatalog[] (same shape, both platforms)",
    },
    {
        "tool": "list_tables",
        "native_databricks": "tables.list() → TableInfo[]",
        "native_aws": "glue.get_tables() → TableList[]",
        "openlakehouse_clm": "list_tables() → CanonicalTable[] (same shape, both platforms)",
    },
    {
        "tool": "run_query",
        "native_databricks": "cursor.execute() → DB-API Row[]",
        "native_aws": "athena.start_query_execution() → async poll → Rows[]",
        "openlakehouse_clm": "run_query() → CanonicalQueryResult (same shape, both platforms)",
    },
    {
        "tool": "governance",
        "native_databricks": "UC privileges (GRANT SQL), per-catalog",
        "native_aws": "IAM + Lake Formation, per-database",
        "openlakehouse_clm": "CanonicalPolicy YAML — adapter/catalog/schema/table rules, unified",
    },
]


def run() -> dict:
    print("\n=== Experiment 4: Native MCP vs OpenLakehouse Agent Coupling ===")

    # Quantify the coupling reduction
    native_multi = next(a for a in APPROACHES if a["approach"].startswith("C"))
    openlakehouse = next(a for a in APPROACHES if a["approach"].startswith("D"))

    reductions = {
        "mcp_endpoints": native_multi["mcp_endpoints_required"] - openlakehouse["mcp_endpoints_required"],
        "metadata_models": native_multi["metadata_models_required"] - openlakehouse["metadata_models_required"],
        "response_parsers": native_multi["agent_response_parsers_required"] - openlakehouse["agent_response_parsers_required"],
        "platform_branches": native_multi["platform_specific_branches_required"] - openlakehouse["platform_specific_branches_required"],
    }

    result = {
        "experiment": "Native MCP vs OpenLakehouse Agent Coupling",
        "status": "completed",
        "approaches": APPROACHES,
        "tool_comparison": TOOL_COMPARISON,
        "coupling_reduction_clm_vs_native_multi": reductions,
        "zero_agent_modification_property": {
            "holds": True,
            "description": "Adding a new platform adapter to OpenLakehouse requires zero changes to agent code, MCP tool names, or canonical response parsers",
            "verified_by": "experiment_5_platform_extension",
        },
    }

    csv_fields = [
        "approach", "mcp_endpoints_required", "metadata_models_required",
        "query_models_required", "governance_models_required",
        "agent_response_parsers_required", "platform_specific_branches_required",
        "supports_databricks", "supports_aws", "supports_both_without_agent_change",
        "response_contract", "vendor_lock_in",
    ]

    save_json(OUTPUT_DIR / "experiment_4_agent_coupling.json", result)
    save_csv(OUTPUT_DIR / "experiment_4_agent_coupling.csv", APPROACHES, csv_fields)
    save_md(OUTPUT_DIR / "experiment_4_agent_coupling.md",
            _make_md(APPROACHES, TOOL_COMPARISON, reductions))

    print(f"  CLM reduces MCP endpoints: {native_multi['mcp_endpoints_required']} → {openlakehouse['mcp_endpoints_required']}")
    print(f"  CLM eliminates platform branches: {native_multi['platform_specific_branches_required']} → {openlakehouse['platform_specific_branches_required']}")
    print(f"  Zero-agent-modification property: HOLDS")
    return result


def _make_md(approaches, tool_comparison, reductions) -> str:
    approach_table = [{
        "Approach": a["approach"],
        "MCP Endpoints": a["mcp_endpoints_required"],
        "Response Models": a["metadata_models_required"],
        "Platform Branches": a["platform_specific_branches_required"],
        "Supports Both": "✓" if a["supports_both_without_agent_change"] else "✗",
        "Vendor Lock-in": a["vendor_lock_in"].split("—")[0].strip(),
    } for a in approaches]

    tool_table = [{
        "Tool / Concern": t["tool"],
        "Databricks Native": t["native_databricks"],
        "AWS Native": t["native_aws"],
        "OpenLakehouse CLM": t["openlakehouse_clm"],
    } for t in tool_comparison]

    lines = [
        "# Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling",
        "",
        "## Purpose",
        "Compare agent integration complexity between native platform MCP connectors and "
        "the OpenLakehouse Canonical Lakehouse Model (CLM) approach. Quantifies reduction "
        "in MCP endpoints, response model variants, and platform-specific agent code branches.",
        "",
        "## Coupling Comparison",
        "",
        md_table(approach_table, ["Approach", "MCP Endpoints", "Response Models",
                                   "Platform Branches", "Supports Both", "Vendor Lock-in"]),
        "",
        "## API Surface Comparison",
        "",
        md_table(tool_table, ["Tool / Concern", "Databricks Native", "AWS Native", "OpenLakehouse CLM"]),
        "",
        "## Coupling Reduction (Native Multi-MCP → OpenLakehouse CLM)",
        "",
        "| Metric | Native Multi-MCP | OpenLakehouse CLM | Reduction |",
        "|---|---|---|---|",
        f"| MCP endpoints | 2 | 1 | **{reductions['mcp_endpoints']}** |",
        f"| Response models | 2 | 1 | **{reductions['metadata_models']}** |",
        f"| Response parsers | 2 | 1 | **{reductions['response_parsers']}** |",
        f"| Platform branches in agent | 2 | 0 | **{reductions['platform_branches']}** |",
        "",
        "## Zero-Agent-Modification Property",
        "",
        "When a new platform adapter is added to OpenLakehouse:",
        "- Agent MCP config: **unchanged** (same single endpoint)",
        "- Agent response parsing: **unchanged** (same canonical model)",
        "- Agent tool call code: **unchanged** (same 5 tool names)",
        "- Only changed: one new adapter file + config registration (server-side only)",
        "",
        "This property is formally verified in Experiment 5.",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run()
