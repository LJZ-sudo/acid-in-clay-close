# -*- coding: utf-8 -*-
"""
ReAct Agent for Phase 3 Analysis

Implements a Reason-Act loop where an LLM:
  1. Observes data (Phase 1 exploration results)
  2. Thinks about what analysis to perform next
  3. Calls a tool (Phase 3 analysis function)
  4. Observes the result
  5. Decides next action — or stops
  6. Repeats until satisfied

This replaces the hard-coded if/else decision logic in the pipeline
agent with LLM-driven reasoning.

The analysis steps (3-7) after the ReAct loop remain the same:
  Load data → Build prompt → Call LLM for report → Generate HTML.

Version: 2.0
Date: 2026-02-06
"""

import sys
import json
import time
import re
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# ============================================================
# Path setup
# ============================================================
PHASE3V2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE3V2_ROOT.parent

sys.path.insert(0, str(PHASE3V2_ROOT))
sys.path.insert(0, str(CLOSE_ROOT))

from tools import (
    tool_explore_data,
    tool_prepare_data,
    tool_train_models,
    tool_confinement,
    tool_meyer_neldel,
    tool_cross_material,
)
from tool_schemas import get_tools_description_for_prompt, TOOL_NAME_SET

# Directories
PHASE1_RESULTS_DIR = CLOSE_ROOT / "output" / "phase1_results"
PHASE3V2_OUTPUT_DIR = CLOSE_ROOT / "output" / "phase3v2_results"
DEEP_ANALYSIS_DIR = CLOSE_ROOT / "output" / "deep_analysis"


# ============================================================
# ReAct Agent
# ============================================================

class ReactPhase3Agent:
    """
    ReAct-style Agent that uses LLM reasoning to autonomously decide
    which Phase 3 analyses to run, in what order, and with what parameters.
    """

    def __init__(
        self,
        material: str = "S8",
        decision_model: str = "anthropic/claude-sonnet-4",
        report_model: str = "anthropic/claude-opus-4.5",
        verbose: bool = True,
        max_iterations: int = 10,
        openai_direct: bool = False,
        openai_api_key: str = "",
    ):
        self.material = material
        self.decision_model = decision_model
        self.report_model = report_model
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.openai_direct = openai_direct
        self.openai_api_key = openai_api_key

        # State
        self.thought_log: List[Dict[str, Any]] = []
        self.tool_results: Dict[str, Any] = {}
        self.conversation: List[Dict[str, str]] = []
        self.execution_log: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None

        # Derived paths (set during execution)
        self._csv_path: Optional[Path] = None
        self._models_dir: Optional[Path] = None

    def log(self, msg: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "level": level, "message": msg}
        self.execution_log.append(entry)
        if self.verbose:
            prefix = {
                "INFO": "[ReAct]",
                "THINK": "  [Thought]",
                "ACT": "  [Action]",
                "OBS": "  [Observation]",
                "STEP": "\n[ReAct STEP]",
                "WARN": "[ReAct WARN]",
                "ERROR": "[ReAct ERROR]",
                "RESULT": "  [Result]",
            }
            print(f"{prefix.get(level, '[ReAct]')} {msg}")

    # ================================================================
    # Step 1: Data exploration (same as pipeline)
    # ================================================================

    def step1_explore(self) -> Dict[str, Any]:
        """Explore Phase 1 data to provide context for the ReAct loop."""
        self.log("Step 1: Exploring Phase 1 data", "STEP")
        result = tool_explore_data(PHASE1_RESULTS_DIR)
        if not result.get("success"):
            self.log(f"Data exploration failed: {result.get('error')}", "ERROR")
            return result
        self.tool_results["explore_data"] = result
        self.log(f"Found {result['n_files']} samples, {result['n_materials']} materials", "RESULT")
        return result

    # ================================================================
    # Step 2: ReAct loop — LLM decides which tools to call
    # ================================================================

    def step2_react_loop(self) -> Dict[str, Any]:
        """
        Main ReAct loop: LLM reasons about data → decides tool → executes → observes.
        Continues until LLM outputs FINISH or max iterations reached.
        """
        self.log("Step 2: Starting ReAct reasoning loop", "STEP")
        self.log(f"Decision model: {self.decision_model}", "INFO")
        self.log(f"Max iterations: {self.max_iterations}", "INFO")

        explore = self.tool_results.get("explore_data")
        if not explore:
            explore = self.step1_explore()
            if not explore.get("success"):
                return {"success": False, "error": "Cannot explore data"}

        # Build initial conversation
        self.conversation = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_initial_user_message(explore)},
        ]

        tools_called = []
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            self.log(f"--- Iteration {iteration}/{self.max_iterations} ---", "INFO")

            # Ask LLM for next action
            response = self._call_decision_llm()
            if response is None:
                self.log("LLM call failed, stopping loop", "ERROR")
                break

            # Parse thought and action
            thought, action, action_params = self._parse_react_response(response)

            if thought:
                self.log(thought[:200], "THINK")
                self.thought_log.append({
                    "iteration": iteration,
                    "thought": thought,
                    "action": action,
                })

            # Check for FINISH
            if action == "FINISH":
                self.log("LLM decided: FINISH — all analyses complete", "ACT")
                # Add assistant message to conversation
                self.conversation.append({"role": "assistant", "content": response})
                break

            if action not in TOOL_NAME_SET:
                self.log(f"Unknown action '{action}', asking LLM to retry", "WARN")
                self.conversation.append({"role": "assistant", "content": response})
                self.conversation.append({
                    "role": "user",
                    "content": f"Unknown tool '{action}'. Available tools: {', '.join(sorted(TOOL_NAME_SET))} or FINISH. Please try again."
                })
                continue

            # Check dependencies
            dep_ok, dep_msg = self._check_dependencies(action)
            if not dep_ok:
                self.log(f"Dependency not met: {dep_msg}", "WARN")
                self.conversation.append({"role": "assistant", "content": response})
                self.conversation.append({
                    "role": "user",
                    "content": f"Cannot run '{action}': {dep_msg}. Please run the required tool first or choose another action."
                })
                continue

            # Execute tool
            self.log(f"Calling tool: {action}", "ACT")
            tools_called.append(action)
            tool_result = self._execute_tool(action, action_params)

            # Build observation
            observation = self._summarize_result(action, tool_result)
            self.log(observation[:300], "OBS")

            # Update conversation
            self.conversation.append({"role": "assistant", "content": response})
            self.conversation.append({
                "role": "user",
                "content": f"**Observation** (result of `{action}`):\n\n{observation}\n\nBased on this result, what should we do next? Think step by step, then choose the next tool or FINISH."
            })

        if iteration >= self.max_iterations:
            self.log(f"Reached max iterations ({self.max_iterations})", "WARN")

        self.log(f"ReAct loop completed: {len(tools_called)} tools called", "RESULT")
        self.log(f"Tools called: {tools_called}", "RESULT")

        return {
            "success": True,
            "iterations": iteration,
            "tools_called": tools_called,
            "thought_log": self.thought_log,
        }

    # ================================================================
    # Steps 3-7: Same as pipeline agent
    # ================================================================

    def step3_load_all_data(self) -> Dict[str, Any]:
        self.log("Step 3: Loading all data", "STEP")
        from agent import Phase3Agent
        helper = Phase3Agent(material=self.material, verbose=False)
        data = helper.step3_load_all_data()
        self.tool_results["all_data"] = data
        self.log(f"Phase1: {len(data.get('phase1', []))} samples, "
                 f"Phase2: {len(data.get('phase2_reports', []))} reports, "
                 f"Phase3: {len(data.get('phase3', {}))} ML results", "RESULT")
        return data

    def step4_build_prompt(self) -> str:
        self.log("Step 4: Building enhanced prompt", "STEP")
        from enhanced_prompts import build_enhanced_deep_analysis_prompt
        data = self.tool_results.get("all_data")
        if not data:
            data = self.step3_load_all_data()

        # Inject ReAct reasoning summary into prompt
        reasoning_summary = self._build_reasoning_summary()

        prompt = build_enhanced_deep_analysis_prompt(
            material=self.material,
            phase1_data=data.get("phase1", []),
            phase2_reports=data.get("phase2_reports", []),
            phase3_results=data.get("phase3", {}),
            knowledge=data.get("knowledge", {}),
        )

        # Append agent reasoning context
        if reasoning_summary:
            prompt += f"\n\n---\n## Agent Reasoning Context\n\n{reasoning_summary}\n"

        self.tool_results["prompt"] = prompt
        self.log(f"Prompt length: {len(prompt)} chars", "RESULT")

        DEEP_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        prompt_file = DEEP_ANALYSIS_DIR / f"{self.material}_react_enhanced_prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        self.log(f"Prompt saved: {prompt_file.name}", "RESULT")
        return prompt

    def step5_generate_report(self, max_tokens: int = 32000) -> Optional[str]:
        self.log("Step 5: Generating enhanced deep analysis report", "STEP")
        self.log(f"Report model: {self.report_model}", "INFO")

        prompt = self.tool_results.get("prompt")
        if not prompt:
            prompt = self.step4_build_prompt()

        system_prompt = (
            "You are a world-class expert in electrochemistry, solid-state ionic "
            "conductors, and proton conduction mechanisms in nanoconfined materials. "
            "You are also proficient in machine learning and statistical analysis. "
            "Provide deep, comprehensive, scientifically rigorous analysis, "
            "fully leveraging the ML quantitative results provided."
        )

        # ── Choose API endpoint ──────────────────────────────────
        if self.openai_direct and self.openai_api_key:
            # Direct OpenAI API (api.openai.com)
            api_url = "https://api.openai.com/v1/chat/completions"
            # OpenAI model name: strip 'openai/' prefix if present
            model_name = self.report_model
            if model_name.startswith("openai/"):
                model_name = model_name[len("openai/"):]
            headers = {
                "Authorization": f"Bearer {self.openai_api_key}",
                "Content-Type": "application/json",
            }
            self.log(f"Using OpenAI direct API → model: {model_name}", "INFO")
        else:
            # OpenRouter API (default)
            try:
                from config.api_config import OPENROUTER_CONFIG
            except ImportError:
                self.log("Cannot import API config", "ERROR")
                return None
            api_url = OPENROUTER_CONFIG["base_url"]
            model_name = self.report_model
            headers = {
                "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/eis-data-analysis",
                "X-Title": f"EIS ReAct Agent - {self.material}",
            }
            self.log(f"Using OpenRouter API → model: {model_name}", "INFO")

        # GPT-5.x uses 'max_completion_tokens'; older/OpenRouter models use 'max_tokens'
        if self.openai_direct and self.openai_api_key:
            token_param = "max_completion_tokens"
        else:
            token_param = "max_tokens"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
            token_param: max_tokens,
        }

        try:
            t0 = time.time()
            resp = requests.post(
                api_url,
                headers=headers, json=payload, timeout=600,
            )
            elapsed = time.time() - t0

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    error = choices[0].get("error")
                    if error:
                        self.log(f"API error: {error}", "ERROR")
                        return None
                    usage = data.get("usage", {})
                    self.log(f"Report generated! Time: {elapsed:.1f}s", "RESULT")
                    self.log(f"Tokens: in={usage.get('prompt_tokens','?')}, "
                             f"out={usage.get('completion_tokens','?')}", "RESULT")
                    self._save_report(content)
                    return content
            else:
                self.log(f"HTTP {resp.status_code}: {resp.text[:300]}", "ERROR")
                return None
        except Exception as e:
            self.log(f"API exception: {str(e)[:200]}", "ERROR")
            return None

    def step7_generate_full_report(self) -> Dict[str, Any]:
        self.log("Step 7: Generating full HTML report with figures", "STEP")
        from report_generator import generate_full_report

        # Try react-specific report first, fall back to standard
        md_path = DEEP_ANALYSIS_DIR / f"{self.material}_react_enhanced_analysis.md"
        if not md_path.exists():
            md_path = DEEP_ANALYSIS_DIR / f"{self.material}_enhanced_deep_mechanism_analysis.md"
        if not md_path.exists():
            self.log(f"No analysis MD found", "ERROR")
            return {"success": False, "error": "No analysis MD"}

        output_html = DEEP_ANALYSIS_DIR / f"{self.material}_react_full_report.html"

        # Build agent log for the report
        agent_log = {
            "mode": "react",
            "tools_called": [e["action"] for e in self.thought_log if e["action"] != "FINISH"],
            "thought_log": self.thought_log,
            "iterations": len(self.thought_log),
            "elapsed_seconds": round(time.time() - self.start_time, 1) if self.start_time else None,
            "report_model": self.report_model,
            "decision_model": self.decision_model,
        }

        try:
            out = generate_full_report(
                md_path, PHASE3V2_OUTPUT_DIR, output_html, self.material,
                agent_log=agent_log,
            )
            self.log(f"Full report generated: {output_html.name}", "RESULT")
            return {"success": True, "output_path": out}
        except Exception as e:
            self.log(f"Report generation failed: {e}", "ERROR")
            return {"success": False, "error": str(e)}

    # ================================================================
    # Full pipeline
    # ================================================================

    def run_full_pipeline(
        self,
        skip_llm: bool = False,
        max_tokens: int = 32000,
    ) -> Dict[str, Any]:
        """Run the complete ReAct agent pipeline: explore → reason → analyze → report."""
        self.start_time = time.time()
        self.log("=" * 70, "INFO")
        self.log("ReAct Phase 3 Agent starting", "INFO")
        self.log(f"Material: {self.material}", "INFO")
        self.log(f"Decision model: {self.decision_model}", "INFO")
        self.log(f"Report model: {self.report_model}", "INFO")
        self.log("=" * 70, "INFO")

        # Step 1: Explore
        explore = self.step1_explore()
        if not explore.get("success"):
            return {"success": False, "error": "Exploration failed"}

        # Step 2: ReAct loop
        react_result = self.step2_react_loop()

        # Step 3: Load all data
        self.step3_load_all_data()

        # Step 4: Build prompt
        self.step4_build_prompt()

        # Step 5: Generate report
        report = None
        if not skip_llm:
            report = self.step5_generate_report(max_tokens=max_tokens)
        else:
            self.log("Skipping LLM report generation (--skip-llm)", "INFO")

        # Step 7: Full HTML report
        full = self.step7_generate_full_report()

        elapsed = time.time() - self.start_time
        self.log(f"\n{'=' * 70}", "INFO")
        self.log(f"ReAct Agent completed! Total time: {elapsed:.1f}s", "INFO")
        self.log(f"{'=' * 70}", "INFO")

        return {
            "success": True,
            "material": self.material,
            "react_iterations": react_result.get("iterations", 0),
            "tools_called": react_result.get("tools_called", []),
            "report_generated": report is not None,
            "full_report": full,
            "elapsed_seconds": round(elapsed, 1),
        }

    # ================================================================
    # Internal: LLM communication
    # ================================================================

    def _build_system_prompt(self) -> str:
        tools_desc = get_tools_description_for_prompt()
        return f"""You are an autonomous EIS (Electrochemical Impedance Spectroscopy) data analysis agent.
Your task is to analyze Phase 1 experimental results for the {self.material} material and decide which
ML analyses to perform to build a comprehensive picture of the proton conduction mechanisms.

You operate in a ReAct (Reason + Act) loop:
1. **Thought**: Reason about the current state — what do you know, what's missing, what should you do next.
2. **Action**: Choose a tool to call, or FINISH if all necessary analyses are done.
3. **Observation**: You will receive the tool's result.
4. Repeat until you decide to FINISH.

{tools_desc}

## Response Format

You MUST respond in exactly this format:

```
Thought: <your reasoning about what to do next and why>
Action: <tool_name or FINISH>
Action Input: <JSON parameters if the tool accepts any, otherwise {{}}>
```

## Important Rules

- Always start with `explore_data` if you haven't seen the data yet.
- Always run `prepare_data` before tools that need the CSV.
- Always run `train_models` before `confinement_analysis` or `cross_material`.
- `meyer_neldel` only requires `prepare_data`, not `train_models`.
- Think about WHAT the data tells you before deciding the next step.
- When you have run all useful analyses, output Action: FINISH.
- Do NOT repeat a tool that already succeeded.
- Be efficient: typically 4-6 tool calls are sufficient.
"""

    def _build_initial_user_message(self, explore_result: Dict) -> str:
        # Create a clean summary (avoid sending huge JSON)
        summary = {
            "n_files": explore_result.get("n_files"),
            "n_materials": explore_result.get("n_materials"),
            "materials": explore_result.get("summary_by_material"),
            "temp_range_K": explore_result.get("temp_range_K"),
            "Ea_range_eV": explore_result.get("Ea_range_eV"),
            "recommended_analyses": explore_result.get("recommended_analyses"),
        }
        return (
            f"I have already explored the Phase 1 data for you. Here is the summary:\n\n"
            f"```json\n{json.dumps(summary, indent=2, default=str)}\n```\n\n"
            f"The target material is **{self.material}**. Based on this data overview, "
            f"think about what ML analyses would be most valuable, then start calling tools.\n\n"
            f"Remember: respond with Thought / Action / Action Input format."
        )

    def _call_decision_llm(self) -> Optional[str]:
        """Call the decision LLM with the current conversation."""
        try:
            from config.api_config import OPENROUTER_CONFIG
        except ImportError:
            self.log("Cannot import API config", "ERROR")
            return None

        headers = {
            "Authorization": f"Bearer {OPENROUTER_CONFIG['api_key']}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/eis-data-analysis",
            "X-Title": f"EIS ReAct Decision - {self.material}",
        }

        payload = {
            "model": self.decision_model,
            "messages": self.conversation,
            "temperature": 0.3,  # Low temperature for consistent decisions
            "max_tokens": 2000,  # Decisions don't need many tokens
        }

        try:
            t0 = time.time()
            resp = requests.post(
                OPENROUTER_CONFIG["base_url"],
                headers=headers, json=payload, timeout=120,
            )
            elapsed = time.time() - t0
            self.log(f"Decision LLM call: {elapsed:.1f}s", "INFO")

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    return content
            else:
                self.log(f"Decision LLM HTTP {resp.status_code}: {resp.text[:200]}", "ERROR")
                return None
        except Exception as e:
            self.log(f"Decision LLM error: {str(e)[:100]}", "ERROR")
            return None

    def _parse_react_response(self, response: str) -> Tuple[str, str, Dict]:
        """
        Parse LLM response in ReAct format:
          Thought: ...
          Action: tool_name or FINISH
          Action Input: {...}
        """
        thought = ""
        action = ""
        action_input = {}

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\Z)", response, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        # Extract Action
        action_match = re.search(r"Action:\s*(\S+)", response)
        if action_match:
            action = action_match.group(1).strip().strip("`")

        # Extract Action Input
        input_match = re.search(r"Action Input:\s*(\{.*?\})", response, re.DOTALL)
        if input_match:
            try:
                action_input = json.loads(input_match.group(1))
            except json.JSONDecodeError:
                action_input = {}

        # Fallback: if no explicit format, try to infer
        if not action:
            lower = response.lower()
            if "finish" in lower and ("all" in lower or "complete" in lower or "done" in lower):
                action = "FINISH"
            # Check if any tool name is mentioned as a clear call
            for tool_name in TOOL_NAME_SET:
                if f"action: {tool_name}" in lower or f"call `{tool_name}`" in lower:
                    action = tool_name
                    break

        return thought, action, action_input

    # ================================================================
    # Internal: Tool execution
    # ================================================================

    def _check_dependencies(self, action: str) -> Tuple[bool, str]:
        """Check if tool dependencies are satisfied."""
        from tool_schemas import TOOL_SCHEMAS
        schema = next((t for t in TOOL_SCHEMAS if t["name"] == action), None)
        if not schema:
            return False, f"Unknown tool: {action}"
        for dep in schema.get("requires", []):
            if dep not in self.tool_results:
                return False, f"Requires '{dep}' to be run first"
        return True, ""

    def _execute_tool(self, action: str, params: Dict) -> Dict[str, Any]:
        """Execute a tool and store its result."""
        try:
            if action == "explore_data":
                result = tool_explore_data(PHASE1_RESULTS_DIR)

            elif action == "prepare_data":
                result = tool_prepare_data(PHASE1_RESULTS_DIR, PHASE3V2_OUTPUT_DIR)
                if result.get("success") and result.get("csv_path"):
                    self._csv_path = Path(result["csv_path"])

            elif action == "train_models":
                if not self._csv_path:
                    return {"success": False, "error": "No CSV path — run prepare_data first"}
                result = tool_train_models(self._csv_path, PHASE3V2_OUTPUT_DIR)
                if result.get("success") and result.get("models_dir"):
                    self._models_dir = Path(result["models_dir"])

            elif action == "confinement_analysis":
                if not self._csv_path or not self._models_dir:
                    return {"success": False, "error": "Missing CSV or models — run prerequisites first"}
                T_low = params.get("T_low", 230.0)
                T_high = params.get("T_high", 270.0)
                result = tool_confinement(self._csv_path, self._models_dir, PHASE3V2_OUTPUT_DIR,
                                          T_low=T_low, T_high=T_high)

            elif action == "meyer_neldel":
                if not self._csv_path:
                    return {"success": False, "error": "No CSV path — run prepare_data first"}
                materials = params.get("materials", None)
                result = tool_meyer_neldel(self._csv_path, PHASE3V2_OUTPUT_DIR, materials=materials)

            elif action == "cross_material":
                if not self._csv_path or not self._models_dir:
                    return {"success": False, "error": "Missing CSV or models — run prerequisites first"}
                result = tool_cross_material(self._csv_path, self._models_dir, PHASE3V2_OUTPUT_DIR)

            else:
                result = {"success": False, "error": f"Unknown tool: {action}"}

            self.tool_results[action] = result
            return result

        except Exception as e:
            error_result = {"success": False, "error": str(e)}
            self.tool_results[action] = error_result
            self.log(f"Tool '{action}' raised exception: {str(e)[:200]}", "ERROR")
            return error_result

    def _summarize_result(self, action: str, result: Dict) -> str:
        """Create a concise text summary of a tool result for the LLM."""
        if not result.get("success"):
            return f"FAILED: {result.get('error', 'Unknown error')}"

        lines = [f"SUCCESS. Key results:"]

        if action == "explore_data":
            lines.append(f"- {result.get('n_files')} samples, {result.get('n_materials')} materials")
            lines.append(f"- Materials: {result.get('summary_by_material')}")
            lines.append(f"- Temp range: {result.get('temp_range_K')} K")
            lines.append(f"- Ea range: {result.get('Ea_range_eV')} eV")
            lines.append(f"- Recommended: {result.get('recommended_analyses')}")

        elif action == "prepare_data":
            lines.append(f"- CSV created: {result.get('n_rows')} rows, {result.get('n_samples')} samples")
            lines.append(f"- Columns: {result.get('columns')}")
            lines.append(f"- Path: {result.get('csv_path')}")

        elif action == "train_models":
            s60 = result.get("s60_metrics", {})
            s8 = result.get("s8_metrics", {})
            delta = result.get("delta_Ea_stats", {})
            lines.append(f"- S60 Baseline: R2={s60.get('r2',0):.4f}, CV_R2={s60.get('cv_r2_mean',0):.4f}, MAE={s60.get('mae_eV',0):.4f} eV")
            lines.append(f"- S8 Confinement: R2={s8.get('r2',0):.4f}, CV_R2={s8.get('cv_r2_mean',0):.4f}, MAE={s8.get('mae_eV',0):.4f} eV")
            lines.append(f"- delta_Ea: mean={delta.get('mean',0):.4f} +/- {delta.get('std',0):.4f} eV")

        elif action == "confinement_analysis":
            ov = result.get("overall", {})
            lines.append(f"- Overall delta_Ea: {ov.get('mean',0):.4f} +/- {ov.get('std',0):.4f} eV")
            for zone in ["low_T_under_230K", "mid_T_230_270K", "high_T_over_270K"]:
                d = result.get(zone, {})
                if d.get("mean") is not None:
                    lines.append(f"- {zone}: delta_Ea={d['mean']:.4f} eV (n={d.get('n',0)})")
            tt = result.get("low_vs_high_T_ttest", {})
            if tt:
                lines.append(f"- Low vs High T t-test: t={tt.get('t_statistic',0):.3f}, p={tt.get('p_value',0):.6f}")
            lf = result.get("delta_Ea_vs_T_linear_fit", {})
            if lf:
                lines.append(f"- Linear trend: slope={lf.get('slope_per_K',0):.6f} eV/K, R2={lf.get('r_squared',0):.4f}")

        elif action == "meyer_neldel":
            for sys_name, data in result.get("results", {}).items():
                emn = data.get("E_MN_eV")
                if emn is not None:
                    lines.append(f"- {sys_name}: E_MN={emn:.4f} eV, R2={data.get('r_squared',0):.4f}")

        elif action == "cross_material":
            for mat, data in result.get("by_material", {}).items():
                lines.append(f"- {mat}: alpha={data.get('mean_alpha',0):.3f}+/-{data.get('std_alpha',0):.3f}, n={data.get('n',0)}")

        return "\n".join(lines)

    def _build_reasoning_summary(self) -> str:
        """Build a summary of the agent's reasoning for inclusion in the final prompt."""
        if not self.thought_log:
            return ""
        lines = [
            "The following analysis was performed by an autonomous ReAct agent that "
            "reasoned about the data and decided which analyses to run:\n"
        ]
        for entry in self.thought_log:
            lines.append(f"**Step {entry['iteration']}** — Action: `{entry['action']}`")
            # Truncate long thoughts
            thought = entry["thought"]
            if len(thought) > 300:
                thought = thought[:300] + "..."
            lines.append(f"> {thought}\n")
        return "\n".join(lines)

    def _save_report(self, content: str):
        """Save the generated analysis report."""
        DEEP_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_file = DEEP_ANALYSIS_DIR / f"{self.material}_react_enhanced_analysis.md"
        header = (
            f"# {self.material} ReAct Agent Enhanced Deep Mechanism Analysis\n\n"
            f"**Generated**: {ts}\n"
            f"**Decision model**: {self.decision_model}\n"
            f"**Report model**: {self.report_model}\n"
            f"**Analysis mode**: Phase3 v2.0 ReAct Agent\n"
            f"**Data source**: Phase 1 + Phase 3 ML (agent-selected analyses)\n\n"
            f"---\n\n"
        )
        report_file.write_text(header + content, encoding="utf-8")
        self.log(f"Report saved: {report_file.name} ({len(content)} chars)", "RESULT")
