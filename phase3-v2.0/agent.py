# -*- coding: utf-8 -*-
"""
Phase 3 v2.0 Agent 主控模块

Agent 流程:
  Step 1: 检查 Phase 1 数据 → 数据探查
  Step 2: 判断是否需要运行 Phase 3 → 自动决策
  Step 3: 加载所有数据（Phase 1 + Phase 2 + Phase 3 结果 + 知识库）
  Step 4: 构建增强版 Prompt
  Step 5: 调用 LLM 生成深度报告
  Step 6: (可选) 后置验证
  Step 7: 生成综合图文报告 (HTML) — 整合分析文本 + ML 图像 + 数据表格

版本: 2.0
日期: 2026-02-06
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# ============================================================
# 路径设置
# ============================================================
PHASE3V2_ROOT = Path(__file__).resolve().parent
CLOSE_ROOT = PHASE3V2_ROOT.parent

# 第一轮 standalone 化：只使用 close 自身模块
sys.path.insert(0, str(CLOSE_ROOT))

# 导入本模块工具
from tools import (
    tool_explore_data,
    tool_prepare_data,
    tool_train_models,
    tool_confinement,
    tool_meyer_neldel,
    tool_cross_material,
    TOOL_REGISTRY,
)

# 输入输出目录
PHASE1_RESULTS_DIR = CLOSE_ROOT / "output" / "phase1_results"
PHASE2_REPORTS_DIR = CLOSE_ROOT / "output" / "phase2_reports"
PHASE3V2_OUTPUT_DIR = CLOSE_ROOT / "output" / "phase3v2_results"
DEEP_ANALYSIS_DIR = CLOSE_ROOT / "output" / "deep_analysis"


class Phase3Agent:
    """
    Phase 3 v2.0 Agent

    自主分析 Phase 1 数据 → 执行 ML 分析 → 收集结果 → 构建增强版 prompt → 生成深度报告
    """

    def __init__(self, material: str = "S8", verbose: bool = True):
        self.material = material
        self.verbose = verbose
        self.results: Dict[str, Any] = {}
        self.execution_log: List[Dict[str, Any]] = []
        self.start_time = None

    def log(self, msg: str, level: str = "INFO"):
        """日志输出"""
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "level": level, "message": msg}
        self.execution_log.append(entry)
        if self.verbose:
            prefix = {"INFO": "[Agent]", "WARN": "[Agent WARN]", "ERROR": "[Agent ERROR]",
                       "STEP": "\n[Agent STEP]", "TOOL": "  [Tool]", "RESULT": "  [Result]"}
            print(f"{prefix.get(level, '[Agent]')} {msg}")

    # ================================================================
    # Step 1: 检查 Phase 1 数据
    # ================================================================

    def step1_check_data(self) -> Dict[str, Any]:
        """检查 Phase 1 数据完整性，返回数据概览"""
        self.log("Step 1: 检查 Phase 1 数据", "STEP")

        if not PHASE1_RESULTS_DIR.exists():
            self.log(f"Phase 1 结果目录不存在: {PHASE1_RESULTS_DIR}", "ERROR")
            return {"success": False}

        result = tool_explore_data(PHASE1_RESULTS_DIR)
        if not result["success"]:
            self.log(f"数据探查失败: {result.get('error')}", "ERROR")
            return result

        self.results["explore"] = result
        self.log(f"找到 {result['n_files']} 个样品文件，{result['n_materials']} 种材料", "RESULT")
        self.log(f"材料分布: {result['summary_by_material']}", "RESULT")
        self.log(f"温度范围: {result['temp_range_K']} K", "RESULT")
        self.log(f"Ea 范围: {result['Ea_range_eV']} eV", "RESULT")
        self.log(f"推荐分析: {result['recommended_analyses']}", "RESULT")
        return result

    # ================================================================
    # Step 2: 判断是否需要运行 Phase 3 分析
    # ================================================================

    def step2_decide_and_run_phase3(self, force: bool = False) -> Dict[str, Any]:
        """判断并执行 Phase 3 分析"""
        self.log("Step 2: 判断并执行 Phase 3 ML 分析", "STEP")

        explore = self.results.get("explore")
        if not explore or not explore.get("success"):
            self.log("缺少 Step 1 数据探查结果，先执行 Step 1", "WARN")
            explore = self.step1_check_data()
            if not explore.get("success"):
                return {"success": False, "error": "Phase 1 数据检查失败"}

        # 检查是否已有 Phase 3 v2.0 结果
        need_run = force
        if not need_run:
            need_run = not self._check_phase3v2_freshness()

        if not need_run:
            self.log("Phase 3 v2.0 结果已存在且为最新，跳过重新计算", "INFO")
            return self._load_existing_phase3v2_results()

        # ---- 决策：根据数据特征选择分析步骤 ----
        plan = explore.get("recommended_analyses", [])
        self.log(f"分析计划: {plan}", "INFO")

        # ---- 执行 ----
        all_results = {}

        # Step 2a: 数据准备
        if "prepare_data" in plan:
            self.log("执行: prepare_data", "TOOL")
            r = tool_prepare_data(PHASE1_RESULTS_DIR, PHASE3V2_OUTPUT_DIR)
            all_results["prepare_data"] = r
            self.log(f"数据准备: {r['n_rows']} 行, {r['n_samples']} 样品" if r["success"] else f"失败: {r.get('error')}", "RESULT")

        # Step 2b: 模型训练
        if "train_models" in plan and all_results.get("prepare_data", {}).get("success"):
            self.log("执行: train_models", "TOOL")
            csv_path = Path(all_results["prepare_data"]["csv_path"])
            r = tool_train_models(csv_path, PHASE3V2_OUTPUT_DIR)
            all_results["train_models"] = r
            if r["success"]:
                s60 = r["s60_metrics"]
                s8 = r["s8_metrics"]
                self.log(f"S60 模型: R²={s60.get('r2', 0):.4f}, CV R²={s60.get('cv_r2_mean', 0):.4f}", "RESULT")
                self.log(f"S8  模型: R²={s8.get('r2', 0):.4f}, CV R²={s8.get('cv_r2_mean', 0):.4f}", "RESULT")
                self.log(f"ΔEa: mean={r['delta_Ea_stats'].get('mean', 0):.4f} eV", "RESULT")
            else:
                self.log(f"模型训练失败", "WARN")

        # Step 2c: 限域效应分析
        if "confinement_analysis" in plan and all_results.get("train_models", {}).get("success"):
            self.log("执行: confinement_analysis", "TOOL")
            csv_path = Path(all_results["prepare_data"]["csv_path"])
            models_dir = Path(all_results["train_models"]["models_dir"])
            r = tool_confinement(csv_path, models_dir, PHASE3V2_OUTPUT_DIR)
            all_results["confinement"] = r
            if r["success"]:
                ov = r["overall"]
                self.log(f"ΔEa 整体: {ov['mean']:.4f} ± {ov['std']:.4f} eV, 95%CI=[{ov.get('ci_95_low'):.4f}, {ov.get('ci_95_high'):.4f}]", "RESULT")
                if r.get("low_vs_high_T_ttest"):
                    tt = r["low_vs_high_T_ttest"]
                    self.log(f"低温 vs 高温: t={tt['t_statistic']:.3f}, p={tt['p_value']:.6f}", "RESULT")

        # Step 2d: Meyer-Neldel
        if "meyer_neldel" in plan and all_results.get("prepare_data", {}).get("success"):
            self.log("执行: meyer_neldel", "TOOL")
            csv_path = Path(all_results["prepare_data"]["csv_path"])
            r = tool_meyer_neldel(csv_path, PHASE3V2_OUTPUT_DIR)
            all_results["meyer_neldel"] = r
            if r["success"]:
                for mat, data in r["results"].items():
                    emn = data.get("E_MN_eV")
                    if emn is not None:
                        self.log(f"Meyer-Neldel [{mat}]: E_MN={emn:.4f} eV, R²={data['r_squared']:.4f}", "RESULT")

        # Step 2e: 跨材料验证
        if "cross_material" in plan and all_results.get("train_models", {}).get("success"):
            self.log("执行: cross_material", "TOOL")
            csv_path = Path(all_results["prepare_data"]["csv_path"])
            models_dir = Path(all_results["train_models"]["models_dir"])
            r = tool_cross_material(csv_path, models_dir, PHASE3V2_OUTPUT_DIR)
            all_results["cross_material"] = r
            if r["success"] and r.get("by_material"):
                for mat, data in r["by_material"].items():
                    self.log(f"跨材料 [{mat}]: α={data['mean_alpha']:.3f}, n={data['n']}", "RESULT")

        self.results["phase3"] = all_results
        return {"success": True, "analyses_run": list(all_results.keys()), "results": all_results}

    # ================================================================
    # Step 3: 加载所有数据
    # ================================================================

    def step3_load_all_data(self) -> Dict[str, Any]:
        """加载 Phase 1 + Phase 2 + Phase 3 + 知识库的所有数据"""
        self.log("Step 3: 加载所有数据", "STEP")
        loaded = {}

        # Phase 1: 原始数据
        loaded["phase1"] = self._load_phase1_data()
        self.log(f"Phase 1: {len(loaded['phase1'])} 个样品数据", "RESULT")

        # Phase 2: 单样品报告
        loaded["phase2_reports"] = self._load_phase2_reports()
        self.log(f"Phase 2: {len(loaded['phase2_reports'])} 份单样品报告", "RESULT")

        # Phase 3 v2.0: ML 结果
        loaded["phase3"] = self._load_phase3v2_results()
        self.log(f"Phase 3: {len(loaded['phase3'])} 项 ML 分析结果", "RESULT")

        # 知识库
        loaded["knowledge"] = self._load_knowledge_base()
        self.log(f"知识库: 已加载", "RESULT")

        self.results["all_data"] = loaded
        return loaded

    # ================================================================
    # Step 4: 构建增强版 Prompt
    # ================================================================

    def step4_build_enhanced_prompt(self) -> str:
        """构建包含 Phase 3 ML 结果的增强版深度分析 prompt"""
        self.log("Step 4: 构建增强版 Prompt", "STEP")

        # 延迟导入 (依赖 Step 3 数据)
        from enhanced_prompts import build_enhanced_deep_analysis_prompt

        all_data = self.results.get("all_data")
        if not all_data:
            self.log("缺少数据，先执行 Step 3", "WARN")
            all_data = self.step3_load_all_data()

        prompt = build_enhanced_deep_analysis_prompt(
            material=self.material,
            phase1_data=all_data["phase1"],
            phase2_reports=all_data["phase2_reports"],
            phase3_results=all_data["phase3"],
            knowledge=all_data["knowledge"],
        )

        self.results["prompt"] = prompt
        self.log(f"Prompt 长度: {len(prompt)} 字符", "RESULT")

        # 保存 prompt
        DEEP_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        prompt_file = DEEP_ANALYSIS_DIR / f"{self.material}_enhanced_deep_prompt.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        self.log(f"Prompt 已保存: {prompt_file.name}", "RESULT")

        return prompt

    # ================================================================
    # Step 5: 调用 LLM 生成报告
    # ================================================================

    def step5_generate_report(self, model: str = "anthropic/claude-opus-4.5",
                              max_tokens: int = 32000) -> Optional[str]:
        """调用 LLM 生成增强版深度分析报告"""
        self.log("Step 5: 调用 LLM 生成增强版深度报告", "STEP")

        prompt = self.results.get("prompt")
        if not prompt:
            self.log("缺少 prompt，先执行 Step 4", "WARN")
            prompt = self.step4_build_enhanced_prompt()

        self.log(f"模型: {model}, max_tokens={max_tokens}", "INFO")
        self.log(f"开始调用 API...", "INFO")

        import requests
        try:
            from config.api_config import OPENROUTER_CONFIG
        except ImportError:
            self.log("无法导入 API 配置", "ERROR")
            return None

        api_key = OPENROUTER_CONFIG['api_key']
        url = OPENROUTER_CONFIG['base_url']

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/eis-data-analysis',
            'X-Title': f'EIS Enhanced Deep Analysis - {self.material}',
        }

        system_prompt = (
            '你是电化学和固态离子导体领域的顶级专家，专门研究限域纳米材料中的质子传导机理。'
            '你同时精通机器学习和统计分析方法。'
            '请提供深入、全面、科学严谨的分析，充分利用提供的 ML 建模定量结果。'
        )

        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.5,
            'max_tokens': max_tokens,
        }

        try:
            t0 = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=600)
            elapsed = time.time() - t0

            if response.status_code == 200:
                result = response.json()
                choices = result.get('choices', [])
                if choices:
                    content = choices[0].get('message', {}).get('content', '')
                    error = choices[0].get('error')
                    if error:
                        self.log(f"API 返回错误: {error}", "ERROR")
                        return None

                    usage = result.get('usage', {})
                    self.log(f"API 调用成功! 耗时: {elapsed:.1f}s", "RESULT")
                    self.log(f"tokens: input={usage.get('prompt_tokens', 'N/A')}, output={usage.get('completion_tokens', 'N/A')}", "RESULT")

                    # 保存报告
                    self._save_report(content, model)
                    return content
            else:
                self.log(f"HTTP {response.status_code}: {response.text[:200]}", "ERROR")
                return None

        except requests.exceptions.Timeout:
            self.log("API 请求超时 (600s)", "ERROR")
            return None
        except Exception as e:
            self.log(f"API 调用异常: {str(e)[:100]}", "ERROR")
            return None

    # ================================================================
    # Step 6 (可选): 后置验证
    # ================================================================

    def step6_post_validation(self) -> Dict[str, Any]:
        """用新报告的 R-N 推荐做 ML-AI 交叉验证"""
        self.log("Step 6: 后置验证 (ML-AI 交叉验证)", "STEP")
        # 此步骤依赖 Step 5 生成的新报告
        # 解析报告中的 R-N 推荐 → 与 ML 数据对比
        # 暂时返回占位结果，后续可扩展
        self.log("后置验证尚待实现（需解析新报告中的 R-N 推荐）", "WARN")
        return {"success": True, "message": "后置验证功能待扩展"}

    # ================================================================
    # Step 7: 生成综合图文报告 (HTML)
    # ================================================================

    def step7_generate_full_report(self) -> Dict[str, Any]:
        """
        生成最终综合报告：将深度分析文本 + ML 图像 + 数据表格整合为
        一份独立的 HTML 报告（类小论文格式）。
        """
        self.log("Step 7: 生成综合图文报告 (HTML)", "STEP")

        from report_generator import generate_full_report

        # 查找增强版深度分析 MD
        analysis_md = DEEP_ANALYSIS_DIR / f"{self.material}_enhanced_deep_mechanism_analysis.md"
        if not analysis_md.exists():
            self.log(f"未找到增强版分析 MD: {analysis_md.name}，请先完成 Step 5", "ERROR")
            return {"success": False, "error": "缺少增强版分析报告"}

        # 输出路径
        output_html = DEEP_ANALYSIS_DIR / f"{self.material}_full_report.html"

        self.log(f"输入: {analysis_md.name}", "INFO")
        self.log(f"图像来源: {PHASE3V2_OUTPUT_DIR}", "INFO")

        # Build agent log for the report
        phase3_results = self.results.get("phase3", {})
        tools_called = phase3_results.get("analyses_run", []) if isinstance(phase3_results, dict) else []
        agent_log = {
            "mode": "pipeline",
            "tools_called": tools_called,
            "thought_log": [],
            "iterations": 0,
            "elapsed_seconds": None,
        }

        try:
            out = generate_full_report(
                analysis_md_path=analysis_md,
                phase3v2_output_dir=PHASE3V2_OUTPUT_DIR,
                output_path=output_html,
                material=self.material,
                agent_log=agent_log,
            )
            self.log(f"综合报告已生成: {output_html.name}", "RESULT")
            self.log(f"报告路径: {out}", "RESULT")
            return {"success": True, "output_path": out}
        except Exception as e:
            self.log(f"报告生成失败: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    # ================================================================
    # 完整流程
    # ================================================================

    def run_full_pipeline(self, force_phase3: bool = False,
                          model: str = "anthropic/claude-opus-4.5",
                          skip_llm: bool = False) -> Dict[str, Any]:
        """
        执行完整 Agent 流程: Step 1-6

        Args:
            force_phase3: 是否强制重新计算 Phase 3
            model: LLM 模型名称
            skip_llm: 是否跳过 LLM 调用 (仅构建 prompt)
        """
        self.start_time = time.time()
        self.log("=" * 70, "INFO")
        self.log(f"Enhanced Deep Analysis Agent 启动", "INFO")
        self.log(f"材料: {self.material}, 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        self.log("=" * 70, "INFO")

        # Step 1
        check = self.step1_check_data()
        if not check.get("success"):
            return {"success": False, "error": "Phase 1 数据检查失败", "log": self.execution_log}

        # Step 2
        phase3 = self.step2_decide_and_run_phase3(force=force_phase3)
        if not phase3.get("success"):
            return {"success": False, "error": "Phase 3 分析失败", "log": self.execution_log}

        # Step 3
        self.step3_load_all_data()

        # Step 4
        prompt = self.step4_build_enhanced_prompt()

        # Step 5
        report = None
        if not skip_llm:
            report = self.step5_generate_report(model=model)
        else:
            self.log("跳过 LLM 调用 (skip_llm=True)", "INFO")

        # Step 7: 综合图文报告
        full_report_result = None
        if report is not None or skip_llm:
            full_report_result = self.step7_generate_full_report()

        elapsed = time.time() - self.start_time
        self.log(f"\n{'=' * 70}", "INFO")
        self.log(f"Agent 流程完成! 总耗时: {elapsed:.1f}s", "INFO")
        self.log(f"{'=' * 70}", "INFO")

        return {
            "success": True,
            "material": self.material,
            "prompt_length": len(prompt),
            "report_generated": report is not None,
            "report_length": len(report) if report else 0,
            "full_report": full_report_result,
            "elapsed_seconds": round(elapsed, 1),
            "log": self.execution_log,
        }

    # ================================================================
    # 内部辅助方法
    # ================================================================

    def _check_phase3v2_freshness(self) -> bool:
        """检查 Phase 3 v2.0 结果是否比 Phase 1 数据更新"""
        metrics_file = PHASE3V2_OUTPUT_DIR / "models" / "metrics.json"
        if not metrics_file.exists():
            return False
        # 取 Phase 1 最新文件时间
        phase1_files = list(PHASE1_RESULTS_DIR.glob("*_analysis_result.json"))
        if not phase1_files:
            return False
        phase1_mtime = max(f.stat().st_mtime for f in phase1_files)
        return metrics_file.stat().st_mtime > phase1_mtime

    def _load_existing_phase3v2_results(self) -> Dict[str, Any]:
        """加载已有的 Phase 3 v2.0 结果"""
        phase3_data = self._load_phase3v2_results()
        self.results["phase3"] = {"loaded_existing": True, **phase3_data}
        return {"success": True, "analyses_run": ["loaded_existing"], "results": phase3_data}

    def _load_phase1_data(self) -> List[Dict]:
        """加载 Phase 1 JSON 数据"""
        data = []
        for jf in sorted(PHASE1_RESULTS_DIR.glob(f"{self.material}*_analysis_result.json")):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                data.append(d)
            except Exception:
                pass
        return data

    def _load_phase2_reports(self) -> List[Dict]:
        """加载 Phase 2 单样品报告"""
        reports = []
        if not PHASE2_REPORTS_DIR.exists():
            return reports
        for rf in sorted(PHASE2_REPORTS_DIR.glob(f"{self.material}*_mechanism_report.md")):
            try:
                content = rf.read_text(encoding="utf-8")
                reports.append({
                    "sample_id": rf.stem.replace("_mechanism_report", ""),
                    "content": content,
                })
            except Exception:
                pass
        return reports

    def _load_phase3v2_results(self) -> Dict[str, Any]:
        """加载 Phase 3 v2.0 所有结构化 JSON 结果"""
        results = {}
        base = PHASE3V2_OUTPUT_DIR
        load_map = {
            "model_metrics": base / "models" / "metrics.json",
            "confinement": base / "confinement" / "summary.json",
            "meyer_neldel": base / "meyer_neldel" / "summary.json",
            "cross_material": base / "cross_material" / "summary.json",
        }
        for key, path in load_map.items():
            if path.exists():
                try:
                    results[key] = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return results

    def _load_knowledge_base(self) -> Dict[str, Any]:
        """加载材料知识库"""
        try:
            from config.material_config import get_clay_type, get_acid_type
            from phase2.data.material_knowledge_base import (
                CLAY_DETAILED_KNOWLEDGE,
                ACID_DETAILED_KNOWLEDGE,
                PROTON_MECHANISM_KNOWLEDGE,
                EIS_MORPHOLOGY_KNOWLEDGE,
                ARRHENIUS_SEGMENTATION_KNOWLEDGE,
            )
            clay_type = get_clay_type(self.material)
            acid_type = get_acid_type(self.material)
            return {
                "clay_type": clay_type,
                "acid_type": acid_type,
                "clay_knowledge": CLAY_DETAILED_KNOWLEDGE.get(clay_type, {}),
                "acid_knowledge": ACID_DETAILED_KNOWLEDGE.get(acid_type, {}),
                "proton_mechanism": PROTON_MECHANISM_KNOWLEDGE,
                "eis_morphology": EIS_MORPHOLOGY_KNOWLEDGE,
                "arrhenius_segmentation": ARRHENIUS_SEGMENTATION_KNOWLEDGE,
            }
        except ImportError as e:
            self.log(f"知识库导入失败: {e}", "WARN")
            return {}

    def _save_report(self, content: str, model: str):
        """保存增强版深度分析报告"""
        DEEP_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        report_file = DEEP_ANALYSIS_DIR / f"{self.material}_enhanced_deep_mechanism_analysis.md"
        header = (
            f"# {self.material} 增强版深度机理分析报告\n\n"
            f"**生成时间**: {ts}\n"
            f"**模型**: {model}\n"
            f"**分析模式**: Phase3 v2.0 Agent Enhanced\n"
            f"**数据来源**: Phase 1 + Phase 3 ML 定量结果\n\n"
            f"---\n\n"
        )
        report_file.write_text(header + content, encoding="utf-8")
        self.log(f"报告已保存: {report_file.name} ({len(content)} 字符)", "RESULT")
