"""Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling

Research Question:
    How does agent integration complexity (MCP endpoints, response model variants,
    platform-specific code branches, governance models) compare between native
    platform connectors and the OpenLakehouse Canonical Lakehouse Model (CLM)?

Method:
    Static analysis comparing four integration approaches across six coupling
    dimensions. No live cloud credentials required. Quantifies Agent Portability
    Metrics: how much agent-side work is required to support N platforms.

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

RESEARCH_QUESTION = (
    "How does agent integration complexity compare between native platform connectors "
    "and the OpenLakehouse Canonical Lakehouse Model (CLM) when an agent must access "
    "data across multiple lakehouse platforms?"
)

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
        "agent_code_changes_when_adding_platform": "Full rewrite or parallel integration required",
        "unified_semantic_contract": False,
        "supports_databricks": True,
        "supports_aws": False,
        "supports_both_without_agent_change": False,
        "response_contract": "Databricks-specific (Unity Catalog REST + SQL Warehouse schema)",
        "vendor_lock_in": "High",
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
        "agent_code_changes_when_adding_platform": "Full rewrite or parallel integration required",
        "unified_semantic_contract": False,
        "supports_databricks": False,
        "supports_aws": True,
        "supports_both_without_agent_change": False,
        "response_contract": "AWS-specific (Glue API + Athena QueryResult schema)",
        "vendor_lock_in": "High",
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
        "agent_code_changes_when_adding_platform": "New endpoint config + parser + branches per operation",
        "unified_semantic_contract": False,
        "supports_databricks": True,
        "supports_aws": True,
        "supports_both_without_agent_change": False,
        "response_contract": "Mixed — agent branches on platform at every step",
        "vendor_lock_in": "High (multiplied; grows linearly with platform count)",
    },
    {
        "approach": "D — OpenLakehouse CLM",
        "description": "Agent connects to OpenLakehouse; receives Canonical Lakehouse Model responses",
        "mcp_endpoints_required": 1,
        "metadata_models_required": 1,
        "query_models_required": 1,
        "governance_models_required": 1,
        "agent_response_parsers_required": 1,
        "platform_specific_branches_required": 0,
        "agent_code_changes_when_adding_platform": "Zero — adapter registered server-side; agent unchanged",
        "unified_semantic_contract": True,
        "supports_databricks": True,
        "supports_aws": True,
        "supports_both_without_agent_change": True,
        "response_contract": "Canonical Lakehouse Model (CLM) — platform-agnostic",
        "vendor_lock_in": "Reduced — agent decoupled from platform-specific schemas via CLM abstraction",
    },
]

TOOL_COMPARISON = [
    {
        "Capability": "list_catalogs",
        "Databricks Native": "catalog.list() → DatabricksCatalogInfo[]",
        "AWS Native": "glue.get_databases() → DatabaseList[]",
        "OpenLakehouse CLM": "list_catalogs() → CanonicalCatalog[] (same shape, both platforms)",
    },
    {
        "Capability": "list_tables",
        "Databricks Native": "tables.list() → TableInfo[]",
        "AWS Native": "glue.get_tables() → TableList[]",
        "OpenLakehouse CLM": "list_tables() → CanonicalTable[] (same shape, both platforms)",
    },
    {
        "Capability": "run_query",
        "Databricks Native": "cursor.execute() → DB-API Row[]",
        "AWS Native": "athena.start_query_execution() → async poll → Rows[]",
        "OpenLakehouse CLM": "run_query() → CanonicalQueryResult (same shape, both platforms)",
    },
    {
        "Capability": "Governance",
        "Databricks Native": "UC GRANT SQL (per-catalog, Databricks-specific)",
        "AWS Native": "IAM + Lake Formation (per-database, AWS-specific)",
        "OpenLakehouse CLM": "CanonicalPolicy YAML — adapter/catalog/schema/table rules, unified",
    },
    {
        "Capability": "Unified Semantic Contract",
        "Databricks Native": "No — agent tied to Databricks API schema",
        "AWS Native": "No — agent tied to AWS API schema",
        "OpenLakehouse CLM": "Yes — CLM defines stable canonical fields independent of platform",
    },
]


def run() -> dict:
    print("\n=== Experiment 4: Native MCP vs OpenLakehouse Agent Coupling ===")

    native_multi = next(a for a in APPROACHES if a["approach"].startswith("C"))
    openlakehouse = next(a for a in APPROACHES if a["approach"].startswith("D"))

    agent_portability_metrics = {
        "mcp_endpoints_eliminated": (
            native_multi["mcp_endpoints_required"] -
            openlakehouse["mcp_endpoints_required"]
        ),
        "response_model_variants_eliminated": (
            native_multi["metadata_models_required"] -
            openlakehouse["metadata_models_required"]
        ),
        "response_parsers_eliminated": (
            native_multi["agent_response_parsers_required"] -
            openlakehouse["agent_response_parsers_required"]
        ),
        "platform_branches_eliminated": (
            native_multi["platform_specific_branches_required"] -
            openlakehouse["platform_specific_branches_required"]
        ),
        "governance_models_required": openlakehouse["governance_models_required"],
        "agent_code_changes_when_adding_platform": openlakehouse["agent_code_changes_when_adding_platform"],
    }

    result = {
        "experiment": "Native MCP vs OpenLakehouse Agent Coupling",
        "research_question": RESEARCH_QUESTION,
        "status": "completed",
        "approaches": APPROACHES,
        "tool_comparison": TOOL_COMPARISON,
        "agent_portability_metrics": agent_portability_metrics,
        "zero_agent_modification_property": {
            "holds": True,
            "description": (
                "Adding a new platform adapter to OpenLakehouse requires zero changes to agent "
                "code, MCP tool names, or canonical response parsers. Verified in Experiment 5."
            ),
            "verified_by": "experiment_5_platform_extension_property_validation",
        },
    }

    csv_fields = [
        "approach", "mcp_endpoints_required", "metadata_models_required",
        "query_models_required", "governance_models_required",
        "agent_response_parsers_required", "platform_specific_branches_required",
        "unified_semantic_contract", "supports_databricks", "supports_aws",
        "supports_both_without_agent_change", "response_contract",
        "agent_code_changes_when_adding_platform", "vendor_lock_in",
    ]

    save_json(OUTPUT_DIR / "experiment_4_agent_coupling.json", result)
    save_csv(OUTPUT_DIR / "experiment_4_agent_coupling.csv", APPROACHES, csv_fields)
    save_md(OUTPUT_DIR / "experiment_4_agent_coupling.md",
            _make_md(APPROACHES, TOOL_COMPARISON, agent_portability_metrics))

    m = agent_portability_metrics
    print(f"  MCP endpoints: {native_multi['mcp_endpoints_required']} → {openlakehouse['mcp_endpoints_required']} ({m['mcp_endpoints_eliminated']} eliminated)")
    print(f"  Platform branches in agent: {native_multi['platform_specific_branches_required']} → {openlakehouse['platform_specific_branches_required']} ({m['platform_branches_eliminated']} eliminated)")
    print(f"  Agent code changes when adding platform: {openlakehouse['agent_code_changes_when_adding_platform']}")
    return result


def _make_md(approaches, tool_comparison, portability_metrics) -> str:
    native_multi = next(a for a in approaches if a["approach"].startswith("C"))
    clm = next(a for a in approaches if a["approach"].startswith("D"))

    approach_table = [{
        "Approach": a["approach"],
        "MCP Endpoints": a["mcp_endpoints_required"],
        "Response Models": a["metadata_models_required"],
        "Platform Branches": a["platform_specific_branches_required"],
        "Unified Contract": "✓" if a["unified_semantic_contract"] else "✗",
        "Supports Both": "✓" if a["supports_both_without_agent_change"] else "✗",
        "Vendor Lock-in": a["vendor_lock_in"].split(" — ")[0] if " — " in a["vendor_lock_in"] else a["vendor_lock_in"],
    } for a in approaches]

    portability_table = [
        {
            "Metric": "MCP endpoints",
            "Native Multi-MCP": native_multi["mcp_endpoints_required"],
            "OpenLakehouse CLM": clm["mcp_endpoints_required"],
            "Improvement": f"−{portability_metrics['mcp_endpoints_eliminated']}",
        },
        {
            "Metric": "Response model variants",
            "Native Multi-MCP": native_multi["metadata_models_required"],
            "OpenLakehouse CLM": clm["metadata_models_required"],
            "Improvement": f"−{portability_metrics['response_model_variants_eliminated']}",
        },
        {
            "Metric": "Agent response parsers",
            "Native Multi-MCP": native_multi["agent_response_parsers_required"],
            "OpenLakehouse CLM": clm["agent_response_parsers_required"],
            "Improvement": f"−{portability_metrics['response_parsers_eliminated']}",
        },
        {
            "Metric": "Platform-specific code branches",
            "Native Multi-MCP": native_multi["platform_specific_branches_required"],
            "OpenLakehouse CLM": clm["platform_specific_branches_required"],
            "Improvement": f"−{portability_metrics['platform_branches_eliminated']}",
        },
        {
            "Metric": "Governance models required",
            "Native Multi-MCP": native_multi["governance_models_required"],
            "OpenLakehouse CLM": portability_metrics["governance_models_required"],
            "Improvement": f"−{native_multi['governance_models_required'] - portability_metrics['governance_models_required']}",
        },
        {
            "Metric": "Agent code changes when adding platform",
            "Native Multi-MCP": "High — new endpoint + parser + branches",
            "OpenLakehouse CLM": "Zero — server-side adapter only",
            "Improvement": "Full elimination",
        },
    ]

    lines = [
        "# Experiment 4 — Native MCP vs OpenLakehouse Agent Coupling",
        "",
        "## Research Question",
        "",
        RESEARCH_QUESTION,
        "",
        "## Method",
        "",
        "Static analysis comparing four integration approaches across six coupling dimensions. "
        "Agent Portability Metrics quantify the reduction in agent-side work when moving from "
        "native multi-platform integration (Approach C) to the OpenLakehouse CLM (Approach D).",
        "",
        "## Agent Portability Metrics",
        "",
        md_table(portability_table,
                 ["Metric", "Native Multi-MCP", "OpenLakehouse CLM", "Improvement"]),
        "",
        "## Approach Comparison",
        "",
        md_table(approach_table, ["Approach", "MCP Endpoints", "Response Models",
                                   "Platform Branches", "Unified Contract",
                                   "Supports Both", "Vendor Lock-in"]),
        "",
        "## Capability Comparison by Tool",
        "",
        md_table(tool_comparison, ["Capability", "Databricks Native", "AWS Native", "OpenLakehouse CLM"]),
        "",
        "## Discussion",
        "",
        "Under native multi-MCP integration (Approach C), every new platform multiplies agent "
        "complexity: additional MCP endpoint configuration, additional response schema parsers, "
        "and additional platform-specific branches in agent code. Governance is also fragmented "
        "across platform-native permission systems (Databricks Unity Catalog GRANT SQL, "
        "AWS IAM + Lake Formation) with no unified audit trail.",
        "",
        "Under OpenLakehouse CLM (Approach D), all platform-specific complexity is contained "
        "server-side in the adapter layer. The agent always receives `CanonicalCatalog`, "
        "`CanonicalTable`, and `CanonicalQueryResult` shapes regardless of which platform the "
        "data resides on. Adding a third platform (e.g. Snowflake, Hive) requires zero agent "
        "code changes — verified in Experiment 5.",
        "",
        "**Vendor lock-in is reduced, not eliminated:** The agent is now coupled to the CLM "
        "contract rather than platform-specific schemas. The CLM is an open internal abstraction "
        "(not a proprietary cloud vendor API), so platform migration risk is substantially "
        "reduced — but the agent does depend on OpenLakehouse as an intermediary layer.",
        "",
        "## Zero-Agent-Modification Property",
        "",
        "When a new platform adapter is added to OpenLakehouse server-side:",
        "- Agent MCP config: **unchanged** (same single endpoint)",
        "- Agent response parsing: **unchanged** (same canonical models)",
        "- Agent tool call code: **unchanged** (same 5 tool names, same parameters)",
        "- Unified governance policy: **unchanged** (same policy.yaml syntax)",
        "",
        "Formally verified in Experiment 5 using a concrete SnowflakeAdapter stub.",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run()
