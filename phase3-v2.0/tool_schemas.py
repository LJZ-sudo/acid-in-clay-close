# -*- coding: utf-8 -*-
"""
Tool Schema Definitions for ReAct Agent

Defines each Phase 3 analysis tool in a structured format that the LLM
can understand and decide when to call.  This file does NOT depend on
any ML/numpy libraries — it only describes metadata.

Version: 2.0
Date: 2026-02-06
"""

TOOL_SCHEMAS = [
    {
        "name": "explore_data",
        "description": (
            "Explore Phase 1 results directory. Returns: number of files, "
            "materials found, sample counts per material, temperature range (K), "
            "Ea range (eV), and recommended analyses. "
            "Call this FIRST to understand the available data."
        ),
        "parameters": {},
        "returns": "dict with keys: n_files, n_materials, summary_by_material, "
                   "temp_range_K, Ea_range_eV, recommended_analyses",
        "requires": [],
    },
    {
        "name": "prepare_data",
        "description": (
            "Extract segment-level data from Phase 1 JSONs and produce "
            "an integrated CSV (columns: sample_id, material, R, N, T_K, "
            "Ea_eV, ln_sigma0, sigma). This CSV is required by all other tools."
        ),
        "parameters": {},
        "returns": "dict with keys: csv_path, n_rows, n_samples, columns",
        "requires": [],
    },
    {
        "name": "train_models",
        "description": (
            "Train two ML models: (1) S60 Baseline Ridge Regression on bulk "
            "H3PO4 data (predicts Ea from R, N, T), and (2) S8 Confinement "
            "Gradient Boosting Regressor on confined material data. Also "
            "computes delta_Ea = Ea_S8_actual - Ea_S60_predicted to quantify "
            "the confinement effect. Returns R2, MAE, CV scores, and delta_Ea stats."
        ),
        "parameters": {},
        "returns": "dict with keys: s60_metrics, s8_metrics, delta_Ea_stats, models_dir",
        "requires": ["prepare_data"],
    },
    {
        "name": "confinement_analysis",
        "description": (
            "Detailed confinement effect analysis: computes delta_Ea by temperature "
            "zone (low T < 230K, mid T 230-270K, high T > 270K), bootstrap 95%% CI, "
            "t-test (low vs high T), and linear fit of delta_Ea vs T. "
            "Generates a scatter plot of delta_Ea vs temperature. "
            "Use this to quantify HOW confinement changes with temperature."
        ),
        "parameters": {
            "T_low": {"type": "float", "default": 230.0,
                      "description": "Temperature boundary for low-T zone (K)"},
            "T_high": {"type": "float", "default": 270.0,
                       "description": "Temperature boundary for high-T zone (K)"},
        },
        "returns": "dict with keys: overall, low_T, mid_T, high_T, t-test, linear_fit",
        "requires": ["train_models"],
    },
    {
        "name": "meyer_neldel",
        "description": (
            "Meyer-Neldel compensation effect analysis: fits ln(sigma_0) vs Ea "
            "to extract the characteristic energy E_MN (eV). Performs fits for: "
            "S8 overall, S60 baseline, S8 high-T (>=270K), S8 low-T (<230K). "
            "Generates a scatter + fit plot. Use this to understand the "
            "entropy-enthalpy compensation and mechanistic transitions."
        ),
        "parameters": {
            "materials": {"type": "list[str]", "default": "null",
                          "description": "Which materials to analyze (default: auto-detect)"},
        },
        "returns": "dict with keys: results (per system: E_MN_eV, r_squared, slope, p_value)",
        "requires": ["prepare_data"],
    },
    {
        "name": "cross_material",
        "description": (
            "Cross-material transfer validation: uses the S8-trained model to "
            "predict Ea for other materials (S6, S14, S16, S95-S97, etc). "
            "Computes alpha = Ea_actual / Ea_predicted for each material. "
            "alpha ~1 means similar confinement to S8, alpha < 1 means weaker, "
            "alpha > 1 means stronger. Use this to assess model transferability "
            "and compare confinement across clay types."
        ),
        "parameters": {},
        "returns": "dict with keys: by_material (n, mean_alpha, std_alpha, mae_eV), overall",
        "requires": ["train_models"],
    },
]


def get_tools_description_for_prompt() -> str:
    """
    Generate a formatted text block describing all available tools,
    suitable for inclusion in a ReAct agent system prompt.
    """
    lines = ["## Available Tools\n"]
    for i, tool in enumerate(TOOL_SCHEMAS, 1):
        lines.append(f"### Tool {i}: `{tool['name']}`")
        lines.append(f"**Description**: {tool['description']}")
        if tool["parameters"]:
            lines.append("**Parameters**:")
            for pname, pinfo in tool["parameters"].items():
                lines.append(f"  - `{pname}` ({pinfo['type']}, default={pinfo['default']}): {pinfo['description']}")
        else:
            lines.append("**Parameters**: none")
        lines.append(f"**Returns**: {tool['returns']}")
        if tool["requires"]:
            lines.append(f"**Requires**: {', '.join(tool['requires'])} must be run first")
        lines.append("")
    return "\n".join(lines)


TOOL_NAME_SET = {t["name"] for t in TOOL_SCHEMAS}
