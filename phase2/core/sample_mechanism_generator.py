# -*- coding: utf-8 -*-
"""
单样品机理报告生成器

功能：
1. 读取 *_analysis_result.json 文件
2. 将数据转换为 mechanism_report.py 需要的格式
3. 调用 build_mechanism_prompt() 生成提示词
4. 调用LLM生成完整机理分析报告

更新日期: 2026-01-26
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import os

# 统一 standalone 路径初始化
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from auto_control.modules.mechanism_report import build_mechanism_prompt
from config.material_config import (
    get_material_info,
    get_material_from_sample_id
)


class SampleMechanismGenerator:
    """
    单样品机理报告生成器
    
    工作流程：
    1. 读取 analysis_result.json
    2. 转换为 mechanism_report.py 需要的 report 格式
    3. 生成提示词
    4. (可选) 调用LLM生成完整报告
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-4-turbo"
    ):
        """
        初始化生成器
        
        Args:
            api_key: OpenRouter API Key (如果需要LLM调用)
            model: LLM模型名称
        """
        self.api_key = api_key
        self.model = model
        self.llm_client = None
        
        # 如果提供了API key，初始化LLM客户端
        if api_key:
            try:
                from phase2.core.multi_model_client import MultiModelClient
                self.llm_client = MultiModelClient(api_key=api_key)
            except ImportError:
                print("[WARN] 无法导入LLM客户端，将只生成提示词")
    
    def load_analysis_result(self, json_path: Path) -> Dict[str, Any]:
        """
        加载分析结果JSON文件
        
        Args:
            json_path: JSON文件路径
            
        Returns:
            分析结果字典
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def convert_to_report_format(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 analysis_result 格式转换为 mechanism_report.py 需要的 report 格式
        
        analysis_result 格式:
        {
            "sample_id": "S8-3-2-1",
            "material_type": "S8",
            "N": 4.286,
            "R": 0.294,
            "L_cm": 0.12,
            "S_cm2": 3.92,
            "temperatures": [...],
            "rb_values": [...],
            "conductivity_values": [...],
            "arrhenius": {
                "success": True,
                "n_segments": 4,
                "segments": [...]
            }
        }
        
        mechanism_report 需要的格式:
        {
            "configuration": {
                "thickness_cm": 0.12,
                "area_cm2": 3.92
            },
            "successful_points": [
                {
                    "temperature_C": ...,
                    "temperature_K": ...,
                    "rb_ohm": ...,
                    "conductivity_S_per_cm": ...,
                    "quality": "good"
                }
            ],
            "arrhenius_analysis": {
                "segments": [...]
            }
        }
        """
        # 基本配置
        report = {
            "configuration": {
                "thickness_cm": analysis_result.get("L_cm", 0.1),
                "area_cm2": analysis_result.get("S_cm2", 1.96),
                "sample_id": analysis_result.get("sample_id", "unknown"),
                "material_type": analysis_result.get("material_type", "unknown"),
                "R": analysis_result.get("R", 0),
                "N": analysis_result.get("N", 0),
            },
            "successful_points": [],
            "arrhenius_analysis": {}
        }
        
        # 转换温度点数据
        temperatures = analysis_result.get("temperatures", [])
        rb_values = analysis_result.get("rb_values", [])
        conductivity_values = analysis_result.get("conductivity_values", [])
        
        # 从 temperature_results 中获取质量信息（如果有）
        temp_results = analysis_result.get("temperature_results", {})
        
        for i, T_K in enumerate(temperatures):
            if T_K is None or T_K <= 0:
                continue
                
            # 获取Rb和电导率
            rb = rb_values[i] if i < len(rb_values) else None
            sigma = conductivity_values[i] if i < len(conductivity_values) else None
            
            # 跳过明显异常的值
            if rb is not None and rb <= 0:
                continue
            if sigma is not None and sigma <= 0:
                continue
            
            # 获取质量等级（从temperature_results）
            T_str = str(int(round(T_K)))
            quality = "good"  # 默认
            if T_str in temp_results:
                fit_quality = temp_results[T_str].get("fit_quality", "")
                if fit_quality:
                    quality = fit_quality
            
            point = {
                "temperature_C": T_K - 273.15,
                "temperature_K": T_K,
                "rb_ohm": rb,
                "conductivity_S_per_cm": sigma,
                "quality": quality,
            }
            report["successful_points"].append(point)
        
        # 转换Arrhenius分析结果
        arrhenius = analysis_result.get("arrhenius", {})
        segments = arrhenius.get("segments", [])
        
        # 转换segment格式
        converted_segments = []
        for seg in segments:
            temp_range = seg.get("temp_range_K", [])
            if isinstance(temp_range, list) and len(temp_range) >= 2:
                T_min_K = temp_range[0]
                T_max_K = temp_range[1]
            else:
                T_min_K = seg.get("T_min_K", 0)
                T_max_K = seg.get("T_max_K", 0)
            
            # 转换为摄氏度
            T_min_C = T_min_K - 273.15 if T_min_K > 0 else None
            T_max_C = T_max_K - 273.15 if T_max_K > 0 else None
            
            # 计算Ea (kJ/mol)，从eV转换
            Ea_eV = seg.get("Ea_eV", 0)
            Ea_kJ_mol = Ea_eV * 96.485 if Ea_eV else None  # 1 eV = 96.485 kJ/mol
            
            converted_seg = {
                "T_range_C": (T_max_C, T_min_C),  # 高温到低温
                "T_range_K": temp_range,
                "data_points": seg.get("n_points", 0),
                "Ea_kJ_per_mol": Ea_kJ_mol,
                "Ea_eV": Ea_eV,
                "slope": seg.get("slope"),
                "intercept": seg.get("intercept"),
                "fit_r2": seg.get("r_squared") or seg.get("R_squared"),
                "quality": seg.get("quality", "good"),
            }
            converted_segments.append(converted_seg)
        
        report["arrhenius_analysis"] = {
            "success": arrhenius.get("success", False),
            "n_segments": len(converted_segments),
            "segments": converted_segments,
        }
        
        return report
    
    def generate_prompt(self, analysis_result: Dict[str, Any]) -> str:
        """
        为单个样品生成机理分析提示词
        
        Args:
            analysis_result: 分析结果字典
            
        Returns:
            机理分析提示词文本
        """
        # 转换格式
        report = self.convert_to_report_format(analysis_result)
        
        # 调用 mechanism_report.py 的函数生成提示词
        prompt = build_mechanism_prompt(report)
        
        # 添加材料特定信息
        sample_id = analysis_result.get("sample_id", "unknown")
        material_id = get_material_from_sample_id(sample_id)
        material_info = get_material_info(material_id)
        
        # 在提示词开头添加材料背景
        material_context = self._build_material_context(
            sample_id, 
            material_info,
            analysis_result.get("R", 0),
            analysis_result.get("N", 0)
        )
        
        return material_context + "\n\n" + prompt
    
    def _build_material_context(
        self, 
        sample_id: str, 
        material_info: Dict,
        R: float,
        N: float
    ) -> str:
        """构建材料背景信息"""
        clay_props = material_info.get("clay_properties", {})
        acid_props = material_info.get("acid_properties", {})
        
        lines = [
            "## 材料背景信息",
            f"- 样品ID: {sample_id}",
            f"- 材料系列: {material_info.get('material_id', 'unknown')}",
            f"- 黏土类型: {material_info.get('clay_type', 'unknown')} ({clay_props.get('chinese_name', '')})",
            f"  - 孔径: {clay_props.get('pore_diameter_nm', 'N/A')} nm",
            f"  - 比表面积: {clay_props.get('surface_area_m2_g', 'N/A')} m²/g",
            f"  - 结构特点: {clay_props.get('structure', 'N/A')}",
            f"- 酸体系: {material_info.get('acid_type', 'unknown')} ({acid_props.get('chinese_name', '')})",
            f"  - 特点: {acid_props.get('features', 'N/A')}",
            f"- 配方参数:",
            f"  - R (酸/水摩尔比): {R:.4f}" if R else "  - R: 未知",
            f"  - N (液/固质量比): {N:.4f}" if N else "  - N: 未知",
        ]
        
        return "\n".join(lines)
    
    def generate_report(
        self,
        analysis_result: Dict[str, Any],
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        生成完整机理报告
        
        Args:
            analysis_result: 分析结果字典
            use_llm: 是否使用LLM生成报告内容
            
        Returns:
            包含提示词和（可选的）LLM报告的字典
        """
        sample_id = analysis_result.get("sample_id", "unknown")
        
        result = {
            "sample_id": sample_id,
            "timestamp": datetime.now().isoformat(),
            "prompt": None,
            "llm_report": None,
            "error": None,
        }
        
        # 生成提示词
        try:
            prompt = self.generate_prompt(analysis_result)
            result["prompt"] = prompt
        except Exception as e:
            result["error"] = f"生成提示词失败: {str(e)}"
            return result
        
        # 如果需要，调用LLM
        if use_llm and self.llm_client:
            try:
                llm_response = self.llm_client.chat(
                    prompt=prompt,
                    model=self.model,
                    temperature=0.3,
                )
                result["llm_report"] = llm_response
            except Exception as e:
                result["error"] = f"LLM调用失败: {str(e)}"
        
        return result
    
    def generate_from_file(
        self,
        json_path: Path,
        output_dir: Optional[Path] = None,
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        从JSON文件生成机理报告
        
        Args:
            json_path: 分析结果JSON文件路径
            output_dir: 输出目录（可选）
            use_llm: 是否使用LLM
            
        Returns:
            报告结果字典
        """
        # 加载数据
        analysis_result = self.load_analysis_result(json_path)
        sample_id = analysis_result.get("sample_id", json_path.stem)
        
        # 生成报告
        result = self.generate_report(analysis_result, use_llm=use_llm)
        
        # 保存输出（如果指定了输出目录）
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存提示词
            if result["prompt"]:
                prompt_path = output_dir / f"{sample_id}_mechanism_prompt.txt"
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(result["prompt"])
                result["prompt_file"] = str(prompt_path)
            
            # 保存LLM报告（如果有）
            if result["llm_report"]:
                report_path = output_dir / f"{sample_id}_mechanism_report.md"
                with open(report_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {sample_id} 机理分析报告\n\n")
                    f.write(f"生成时间: {result['timestamp']}\n\n")
                    f.write("---\n\n")
                    f.write(result["llm_report"])
                result["report_file"] = str(report_path)
        
        return result


def batch_generate_prompts(
    processed_dir: Path,
    output_dir: Path,
    use_llm: bool = False,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    批量生成机理分析提示词
    
    Args:
        processed_dir: 处理结果目录
        output_dir: 输出目录
        use_llm: 是否使用LLM
        api_key: API Key (如果use_llm=True)
        
    Returns:
        批量处理结果统计
    """
    print("\n" + "=" * 60)
    print("批量生成单样品机理分析提示词")
    print("=" * 60)
    
    from config.material_config import (
        MATERIAL_WHITELIST,
        is_material_allowed,
        get_material_from_sample_id
    )
    
    generator = SampleMechanismGenerator(api_key=api_key)
    
    # 收集JSON文件
    all_files = list(processed_dir.glob("*_analysis_result.json"))
    
    # 过滤白名单材料
    json_files = [
        f for f in all_files
        if is_material_allowed(get_material_from_sample_id(f.stem.replace("_analysis_result", "")))
    ]
    
    print(f"[INFO] 发现 {len(all_files)} 个文件，过滤后 {len(json_files)} 个")
    
    # 创建输出目录
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "total": len(json_files),
        "success": 0,
        "failed": 0,
        "files": []
    }
    
    for i, json_file in enumerate(json_files, 1):
        sample_id = json_file.stem.replace("_analysis_result", "")
        print(f"[{i}/{len(json_files)}] 处理 {sample_id}...")
        
        try:
            result = generator.generate_from_file(
                json_file,
                output_dir=output_dir,
                use_llm=use_llm
            )
            
            if result["error"]:
                print(f"  [WARN] {result['error']}")
                results["failed"] += 1
            else:
                results["success"] += 1
                if result.get("prompt_file"):
                    print(f"  [OK] 提示词: {Path(result['prompt_file']).name}")
            
            results["files"].append({
                "sample_id": sample_id,
                "success": result["error"] is None,
                "error": result.get("error"),
            })
            
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            results["failed"] += 1
            results["files"].append({
                "sample_id": sample_id,
                "success": False,
                "error": str(e),
            })
    
    print(f"\n[DONE] 成功: {results['success']}, 失败: {results['failed']}")
    
    return results


# 测试代码
if __name__ == "__main__":
    import argparse
    
    # 解决Windows编码问题
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, Exception):
            pass
    
    parser = argparse.ArgumentParser(description="单样品机理报告生成器")
    parser.add_argument("--input", type=str, help="输入JSON文件路径")
    parser.add_argument("--output", type=str, default="analysis_output/mechanism_prompts", help="输出目录")
    parser.add_argument("--batch", action="store_true", help="批量处理模式")
    parser.add_argument("--processed-dir", type=str, default="historical_data/processed", help="批量处理时的输入目录")
    
    args = parser.parse_args()
    
    if args.batch:
        # 批量模式
        processed_dir = PROJECT_ROOT / args.processed_dir
        output_dir = PROJECT_ROOT / args.output
        results = batch_generate_prompts(processed_dir, output_dir)
    elif args.input:
        # 单文件模式
        generator = SampleMechanismGenerator()
        json_path = Path(args.input)
        output_dir = Path(args.output) if args.output else None
        result = generator.generate_from_file(json_path, output_dir=output_dir)
        
        if result["error"]:
            print(f"[ERROR] {result['error']}")
        else:
            print(f"[OK] 提示词生成成功")
            if result["prompt"]:
                print("\n--- 提示词预览 (前500字符) ---")
                print(result["prompt"][:500] + "...")
    else:
        # 默认测试
        print("使用默认测试文件...")
        test_file = PROJECT_ROOT / "historical_data" / "processed" / "S8-3-2-1_analysis_result.json"
        if test_file.exists():
            generator = SampleMechanismGenerator()
            result = generator.generate_from_file(test_file)
            
            if result["error"]:
                print(f"[ERROR] {result['error']}")
            else:
                print(f"[OK] 提示词生成成功")
                print("\n--- 提示词预览 (前800字符) ---")
                print(result["prompt"][:800] + "...")
        else:
            print(f"[ERROR] 测试文件不存在: {test_file}")
