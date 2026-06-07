"""
Planner Prompts
提示词构建器：为 LLM 生成结构化的实验规划提示词
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from canonical_input.campaign_parser import CampaignConfig


class PromptBuilder:
    """
    提示词构建器
    
    将实验数据、历史信息、优化器建议组装成清晰的 LLM 提示词
    确保 LLM 能够理解实验背景并输出符合 NextExperimentRecipe 的 JSON
    """
    
    def __init__(self, campaign_config: CampaignConfig):
        """
        初始化提示词构建器
        
        Args:
            campaign_config: 实验战役配置
        """
        self.campaign_config = campaign_config
        self.template_dir = Path(__file__).parent
        self.last_prompt_metadata: Dict[str, Any] = {}

    def _read_template(self, filename: str) -> str:
        path = self.template_dir / filename
        return path.read_text(encoding="utf-8")

    def _sha256_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _render_template(self, template: str, values: Dict[str, str]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered
    
    def build_system_prompt(self) -> str:
        """
        构建系统提示词（定义 LLM 的角色和任务）
        
        动态注入领域知识，移除硬编码的材料背景
        
        Returns:
            系统提示词字符串
        """
        # 动态获取领域知识
        domain_knowledge = self.campaign_config.get_domain_knowledge()
        
        # 构建领域知识区块（如果存在）
        domain_knowledge_section = ""
        if domain_knowledge:
            domain_knowledge_section = f"""
## 材料学专家背景与物理约束

{domain_knowledge}
"""
        
        template = self._read_template("planner_system.md")
        system_prompt = self._render_template(template, {
            "campaign_name": self.campaign_config.campaign_name,
            "objective_target": self.campaign_config.get_objective_target(),
            "objective_goal": self.campaign_config.get_objective_goal(),
            "parameter_description": self.campaign_config.get_prompt_description(),
            "domain_knowledge_section": domain_knowledge_section.strip(),
        })
        self.last_prompt_metadata["system_template"] = {
            "path": str(self.template_dir / "planner_system.md"),
            "template_sha256": self._sha256_text(template),
            "rendered_sha256": self._sha256_text(system_prompt),
        }
        
        return system_prompt
    
    def build_user_prompt(
        self,
        current_metrics: Dict[str, float],
        best_historical_metrics: Optional[Dict[str, float]],
        optimizer_suggestion: Dict[str, Any],
        historical_trials_summary: Optional[str] = None,
        physical_features: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建用户提示词（包含具体的实验数据和优化器建议）
        
        Args:
            current_metrics: 当前样品的测试指标
            best_historical_metrics: 历史最优测试指标
            optimizer_suggestion: 贝叶斯优化器推荐的参数
            historical_trials_summary: 历史实验摘要（可选）
            physical_features: 物理特征（包含 Arrhenius 分段 Ea、相变点等）
            
        Returns:
            用户提示词字符串
        """
        physical_features_section = ""
        
        if physical_features:
            physical_features_section = (
                "## 物理特征详情（宽温域 Arrhenius 分析）\n\n"
                + self._format_physical_features(physical_features)
            )
        
        best_historical_section = ""
        if best_historical_metrics:
            best_historical_section = (
                "## 历史最优性能（目标基准）\n\n"
                + self._format_metrics(best_historical_metrics)
            )
            
            objective_name = self.campaign_config.get_objective_target()
            if objective_name in current_metrics and objective_name in best_historical_metrics:
                current_val = current_metrics[objective_name]
                best_val = best_historical_metrics[objective_name]
                improvement = ((current_val - best_val) / best_val) * 100
                
                best_historical_section += (
                    f"\n**性能对比**: 当前样品相比历史最优 "
                    f"{'提升' if improvement > 0 else '下降'} {abs(improvement):.2f}%"
                )
        
        historical_trials_section = ""
        if historical_trials_summary:
            historical_trials_section = (
                "## 历史实验趋势\n\n"
                + historical_trials_summary
            )
        
        deep_analysis_instruction = ""
        if physical_features:
            deep_analysis_instruction = (
                "## 【深度分析指令】\n\n"
                "请结合《材料学专家背景与物理约束》中的理论，深度分析当前样品的 Arrhenius 特征：\n"
                "- **低温区活化能 (Ea_low)** 是否突增？这是否表明发生了相变或退化？\n"
                "- **相变温度 (transition_temps_K)** 的存在是否符合预期？\n"
                "- **Arrhenius 分段数量 (n_segments)** 是否表明材料行为的复杂性？\n\n"
                "在 JSON 的 `reasoning` 字段中，明确判断当前的参数组合是否维持了有效的物理状态，"
                "还是已退化为不理想的行为模式？并以此作为推荐下一步参数的核心依据。\n\n"
                "**关键判断**: 基于 Arrhenius 特征，当前材料是否处于最优物理状态？如果不是，应如何调整参数？"
            )
        
        template = self._read_template("planner_user_template.md")
        user_prompt = self._render_template(template, {
            "current_metrics": self._format_metrics(current_metrics),
            "physical_features_section": physical_features_section,
            "best_historical_section": best_historical_section,
            "historical_trials_section": historical_trials_section,
            "optimizer_suggestion_json": json.dumps(optimizer_suggestion, indent=2, ensure_ascii=False),
            "deep_analysis_instruction": deep_analysis_instruction,
        })
        self.last_prompt_metadata["user_template"] = {
            "path": str(self.template_dir / "planner_user_template.md"),
            "template_sha256": self._sha256_text(template),
            "rendered_sha256": self._sha256_text(user_prompt),
        }
        return user_prompt
    
    def _format_metrics(self, metrics: Dict[str, float]) -> str:
        """
        格式化指标数据为可读字符串
        
        Args:
            metrics: 指标字典
            
        Returns:
            格式化的字符串
        """
        lines = []
        for key, value in metrics.items():
            # 科学计数法格式化
            if isinstance(value, (int, float)):
                if abs(value) < 0.01 or abs(value) > 10000:
                    formatted_value = f"{value:.2e}"
                else:
                    formatted_value = f"{value:.4f}"
            else:
                formatted_value = str(value)
            
            lines.append(f"- **{key}**: {formatted_value}")
        
        return "\n".join(lines)
    
    def _format_physical_features(self, physical_features: Dict[str, Any]) -> str:
        """
        格式化物理特征数据（包含 Arrhenius 分析结果）
        
        Args:
            physical_features: 物理特征字典
            
        Returns:
            格式化的字符串
        """
        lines = []
        
        # 提取关键物理特征
        conductivity = physical_features.get("conductivity_room_temp_S_cm")
        ea_high = physical_features.get("ea_high_temp_eV")
        ea_low = physical_features.get("ea_low_temp_eV")
        n_segments = physical_features.get("n_segments")
        transition_temps = physical_features.get("transition_temps_K", [])
        
        # 格式化输出
        if conductivity is not None:
            lines.append(f"- **室温电导率 (25°C)**: {conductivity:.4e} S/cm")
        
        if ea_high is not None:
            lines.append(f"- **高温区活化能 (Ea_high)**: {ea_high:.4f} eV")
        
        if ea_low is not None:
            lines.append(f"- **低温区活化能 (Ea_low)**: {ea_low:.4f} eV")
            
            # 判断低温区是否异常
            if ea_high is not None and ea_low > ea_high * 1.5:
                lines.append(f"  [WARNING] 低温区 Ea 显著高于高温区 ({ea_low/ea_high:.2f}x)，可能存在相变或退化")
        
        if n_segments is not None:
            lines.append(f"- **Arrhenius 分段数**: {int(n_segments)}")
            if n_segments > 1:
                lines.append(f"  → 材料在不同温度区间表现出不同的传导机制")
        
        if transition_temps:
            temps_str = ", ".join([f"{t:.2f} K ({t-273.15:.2f}°C)" for t in transition_temps])
            lines.append(f"- **相变温度点**: {temps_str}")
            lines.append(f"  → 在这些温度附近，材料的传导行为发生显著变化")
        
        return "\n".join(lines)
    
    def build_historical_summary(
        self,
        trials: List[Dict[str, Any]],
        max_trials: int = 5
    ) -> str:
        """
        构建历史实验摘要
        
        Args:
            trials: 历史实验列表
            max_trials: 最多展示的实验数量
            
        Returns:
            历史摘要字符串
        """
        if not trials:
            return "暂无历史实验数据。"
        
        objective_name = self.campaign_config.get_objective_target()
        
        # 只展示最近的实验
        recent_trials = trials[-max_trials:]
        
        summary_lines = [
            f"共进行了 {len(trials)} 次实验，以下是最近 {len(recent_trials)} 次："
        ]
        
        for i, trial in enumerate(recent_trials, 1):
            params = trial.get("parameters", {})
            objectives = trial.get("objectives", {})
            
            # 格式化参数
            param_str = ", ".join([
                f"{k}={v}" for k, v in params.items()
            ])
            
            # 格式化目标值
            obj_value = objectives.get(objective_name, "N/A")
            if isinstance(obj_value, (int, float)):
                obj_str = f"{obj_value:.2e}" if abs(obj_value) < 0.01 else f"{obj_value:.4f}"
            else:
                obj_str = str(obj_value)
            
            summary_lines.append(
                f"{i}. 参数: [{param_str}] → {objective_name}: {obj_str}"
            )
        
        return "\n".join(summary_lines)
    
    def build_complete_prompt(
        self,
        current_metrics: Dict[str, float],
        best_historical_metrics: Optional[Dict[str, float]],
        optimizer_suggestion: Dict[str, Any],
        historical_trials: Optional[List[Dict[str, Any]]] = None,
        physical_features: Optional[Dict[str, Any]] = None
    ) -> tuple[str, str]:
        """
        构建完整的提示词（系统 + 用户）
        
        Args:
            current_metrics: 当前样品的测试指标
            best_historical_metrics: 历史最优测试指标
            optimizer_suggestion: 贝叶斯优化器推荐的参数
            historical_trials: 历史实验列表（可选）
            physical_features: 物理特征（包含 Arrhenius 分析）
            
        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = self.build_system_prompt()
        
        historical_summary = None
        if historical_trials:
            historical_summary = self.build_historical_summary(historical_trials)
        
        user_prompt = self.build_user_prompt(
            current_metrics=current_metrics,
            best_historical_metrics=best_historical_metrics,
            optimizer_suggestion=optimizer_suggestion,
            historical_trials_summary=historical_summary,
            physical_features=physical_features
        )
        
        return system_prompt, user_prompt

    def get_prompt_metadata(self) -> Dict[str, Any]:
        """返回最近一次构建 prompt 的模板与渲染 hash。"""
        return dict(self.last_prompt_metadata)
