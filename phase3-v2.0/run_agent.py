# -*- coding: utf-8 -*-
"""
Phase 3 v2.0 Agent Entry Point

Supports two agent modes:
  - pipeline (default): Fixed-step automated analysis pipeline
  - react: LLM-driven ReAct reasoning loop for autonomous decisions

Usage:
    cd close

    # Pipeline mode (default)
    python phase3-v2.0/run_agent.py

    # ReAct agent mode
    python phase3-v2.0/run_agent.py --agent-mode react

    # ReAct with skip-llm (only run the reasoning loop, no final report)
    python phase3-v2.0/run_agent.py --agent-mode react --skip-llm

    # Pipeline with specific steps
    python phase3-v2.0/run_agent.py --steps 3-7

    # Specify materials and models
    python phase3-v2.0/run_agent.py --agent-mode react --material S8 --model anthropic/claude-opus-4.5

Version: 2.1
Date: 2026-02-06
"""

import sys
import argparse
from pathlib import Path

# Path setup
PHASE3V2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE3V2_ROOT.parent

sys.path.insert(0, str(PHASE3V2_ROOT))
sys.path.insert(0, str(CLOSE_ROOT))

# Windows encoding fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Phase 3 v2.0 Agent: ML Analysis + Enhanced Deep Mechanism Report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python phase3-v2.0/run_agent.py                                # Pipeline mode (default)
  python phase3-v2.0/run_agent.py --agent-mode react             # ReAct agent mode
  python phase3-v2.0/run_agent.py --agent-mode react --skip-llm  # ReAct reasoning only
  python phase3-v2.0/run_agent.py --steps 7                      # Only generate HTML report
  python phase3-v2.0/run_agent.py --force --model openai/gpt-5.2
        """
    )
    parser.add_argument("--material", default="S8", help="Material ID (default: S8)")
    parser.add_argument("--model", default="anthropic/claude-opus-4.5", help="LLM model for final report")
    parser.add_argument("--decision-model", default="anthropic/claude-sonnet-4",
                        help="LLM model for ReAct decisions (default: claude-sonnet-4)")
    parser.add_argument("--agent-mode", choices=["pipeline", "react"], default="pipeline",
                        help="Agent mode: 'pipeline' (fixed steps) or 'react' (LLM reasoning loop)")
    parser.add_argument("--skip-llm", action="store_true", help="Skip final report LLM call")
    parser.add_argument("--force", action="store_true", help="Force recompute Phase 3 results")
    parser.add_argument("--steps", default="1-7", help="Step range for pipeline mode (e.g. '3-7', '7')")
    parser.add_argument("--max-tokens", type=int, default=32000, help="Max output tokens for report LLM")
    parser.add_argument("--max-iterations", type=int, default=10, help="Max ReAct loop iterations")
    parser.add_argument("--openai-direct", action="store_true",
                        help="Use OpenAI official API directly (not OpenRouter) for report generation")
    parser.add_argument("--openai-key", default="", help="OpenAI API key (for --openai-direct)")
    parser.add_argument("--quiet", action="store_true", help="Reduce output")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f"  Phase 3 v2.0 Agent - Enhanced Deep Analysis")
    print(f"  Mode: {args.agent_mode.upper()}")
    print(f"  Material: {args.material} | Report model: {args.model}")
    if args.openai_direct:
        print(f"  API: OpenAI DIRECT (api.openai.com)")
    else:
        print(f"  API: OpenRouter")
    if args.agent_mode == "react":
        print(f"  Decision model: {args.decision_model} | Max iterations: {args.max_iterations}")
    else:
        print(f"  Steps: {args.steps} | Force recompute: {args.force}")
    print("=" * 70)

    if args.agent_mode == "react":
        return _run_react(args)
    else:
        return _run_pipeline(args)


def _run_react(args):
    """Run the ReAct agent mode."""
    from react_agent import ReactPhase3Agent

    agent = ReactPhase3Agent(
        material=args.material,
        decision_model=args.decision_model,
        report_model=args.model,
        verbose=not args.quiet,
        max_iterations=args.max_iterations,
        openai_direct=args.openai_direct,
        openai_api_key=args.openai_key,
    )

    result = agent.run_full_pipeline(
        skip_llm=args.skip_llm,
        max_tokens=args.max_tokens,
    )

    print("\n" + "=" * 70)
    print("ReAct Agent Summary:")
    print(f"  Iterations: {result.get('react_iterations', 0)}")
    print(f"  Tools called: {result.get('tools_called', [])}")
    print(f"  Report generated: {result.get('report_generated', False)}")
    full = result.get("full_report", {})
    if full and full.get("success"):
        print(f"  Full HTML report: {full['output_path']}")
    print(f"  Total time: {result.get('elapsed_seconds', 0)}s")
    print("=" * 70)

    # Save execution log
    _save_log(agent.execution_log, agent.thought_log, args, mode="react")
    return 0


def _run_pipeline(args):
    """Run the pipeline agent mode."""
    start_step, end_step = _parse_steps(args.steps)

    from agent import Phase3Agent
    agent = Phase3Agent(material=args.material, verbose=not args.quiet)

    if start_step <= 1 <= end_step:
        result = agent.step1_check_data()
        if not result.get("success"):
            print("\n[FAIL] Step 1 failed")
            return 1

    if start_step <= 2 <= end_step:
        result = agent.step2_decide_and_run_phase3(force=args.force)
        if not result.get("success"):
            print("\n[FAIL] Step 2 failed")
            return 1

    if start_step <= 3 <= end_step:
        agent.step3_load_all_data()

    if start_step <= 4 <= end_step:
        prompt = agent.step4_build_enhanced_prompt()
        print(f"\n[INFO] Prompt preview (first 500 chars):")
        print("-" * 40)
        print(prompt[:500])
        print("-" * 40)

    if start_step <= 5 <= end_step and not args.skip_llm:
        report = agent.step5_generate_report(model=args.model, max_tokens=args.max_tokens)
        if report:
            print(f"\n[INFO] Report preview (first 500 chars):")
            print("-" * 40)
            print(report[:500])
            print("-" * 40)
        else:
            print("\n[WARN] Report generation failed")
    elif start_step <= 5 <= end_step:
        print("\n[INFO] Skipping LLM call (--skip-llm)")

    if start_step <= 6 <= end_step:
        agent.step6_post_validation()

    if start_step <= 7 <= end_step:
        full_report = agent.step7_generate_full_report()
        if full_report.get("success"):
            print(f"\n[SUCCESS] Full HTML report: {full_report['output_path']}")
        else:
            print(f"\n[WARN] HTML report failed: {full_report.get('error')}")

    print("\n" + "=" * 70)
    print("Agent pipeline complete!")
    print("=" * 70)

    _save_log(agent.execution_log, [], args, mode="pipeline")
    return 0


def _parse_steps(steps_str: str):
    if "-" in steps_str:
        parts = steps_str.split("-")
        return int(parts[0]), int(parts[1])
    else:
        n = int(steps_str)
        return n, n


def _save_log(execution_log, thought_log, args, mode="pipeline"):
    import json
    from datetime import datetime

    log_dir = CLOSE_ROOT / "output" / "phase3v2_results"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "material": args.material,
        "model": args.model,
        "execution_log": execution_log,
    }
    if mode == "react":
        log_data["decision_model"] = args.decision_model
        log_data["max_iterations"] = args.max_iterations
        log_data["thought_log"] = thought_log

    log_file = log_dir / f"agent_execution_log_{mode}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"[LOG] Execution log saved: {log_file}")


if __name__ == "__main__":
    raise SystemExit(main())
