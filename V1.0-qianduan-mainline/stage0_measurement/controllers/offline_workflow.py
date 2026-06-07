# -*- coding: utf-8 -*-
"""
离线批处理工作流控制器

职责：
1. 扫描和解析数据文件（CHI、DTA）
2. 批量 EIS 分析
3. 多点 Arrhenius 分析
4. 聚合图表输出（PNG，不含 Markdown）

核心原则：
- 纯数据处理，不引入 hardware/automation 模块
- 健壮错误处理，单个文件失败不影响全局
- 高度复用已重构的基础模块

版本：2.0.0 (重构版)
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import traceback


@dataclass
class OfflineConfig:
    """
    离线批处理配置
    
    Attributes:
        data_dir: 数据目录（CHI 文件）
        dta_dir: DTA 文件目录（可选）
        output_dir: 输出目录
        
        chi_file_pattern: CHI 文件匹配模式
        dta_file_pattern: DTA 文件匹配模式
        
        skip_failed_files: 是否跳过失败的文件
        continue_on_error: 遇到错误是否继续
        
        enable_arrhenius: 是否启用 Arrhenius 分析
        enable_reporting: 是否生成报告
        
        material_name: 材料名称
        thickness_cm: 样品厚度 (cm)
        area_cm2: 样品面积 (cm²)
    """
    data_dir: str
    dta_dir: Optional[str] = None
    output_dir: str = "./offline_results"
    
    chi_file_pattern: str = "*.txt"
    dta_file_pattern: str = "*.dta"
    
    skip_failed_files: bool = True
    continue_on_error: bool = True
    
    enable_arrhenius: bool = True
    enable_reporting: bool = True
    
    material_name: str = "Sample"
    thickness_cm: float = 0.12
    area_cm2: float = 1.96


@dataclass
class ProcessingResult:
    """
    单个文件处理结果
    
    Attributes:
        filepath: 文件路径
        success: 是否成功
        temperature_C: 温度 (°C)
        data: 分析结果数据
        error: 错误信息
    """
    filepath: str
    success: bool
    temperature_C: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class BatchResult:
    """
    批处理结果
    
    Attributes:
        total_files: 总文件数
        processed_files: 处理的文件数
        successful_files: 成功的文件数
        failed_files: 失败的文件数
        
        processing_results: 处理结果列表
        aggregated_data: 聚合数据
        
        arrhenius_result: Arrhenius 分析结果
        report_paths: 生成的图表 PNG 路径列表
        
        start_time: 开始时间
        end_time: 结束时间
        duration_seconds: 耗时（秒）
    """
    total_files: int = 0
    processed_files: int = 0
    successful_files: int = 0
    failed_files: int = 0
    
    processing_results: List[ProcessingResult] = field(default_factory=list)
    aggregated_data: Dict[str, Any] = field(default_factory=dict)
    
    arrhenius_result: Optional[Dict[str, Any]] = None
    report_paths: List[str] = field(default_factory=list)
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0


# ============================================================
# 离线批处理工作流
# ============================================================

class OfflineBatchWorkflow:
    """
    离线批处理工作流控制器
    
    纯数据处理调度器，不依赖硬件或自动化模块
    """
    
    def __init__(
        self,
        config: OfflineConfig,
        eis_analyzer: Optional[Callable] = None,
        arrhenius_analyzer: Optional[Callable] = None,
    ):
        """
        初始化工作流
        
        Args:
            config: 离线配置
            eis_analyzer: EIS 分析函数（可选）
            arrhenius_analyzer: Arrhenius 分析函数（可选）
        """
        self.config = config
        self.eis_analyzer = eis_analyzer
        self.arrhenius_analyzer = arrhenius_analyzer
        
        # 创建输出目录
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        # 日志
        self.log_messages: List[str] = []
    
    # ========================================================
    # 主入口：批处理
    # ========================================================
    
    def run_batch_processing(self) -> BatchResult:
        """
        运行完整的批处理流程
        
        Returns:
            BatchResult: 批处理结果
        """
        print("=" * 60)
        print("🚀 开始离线批处理流程")
        print("=" * 60)
        print(f"📁 数据目录: {self.config.data_dir}")
        print(f"📊 输出目录: {self.config.output_dir}")
        print("=" * 60)
        
        result = BatchResult()
        result.start_time = datetime.now()
        
        try:
            # 1. 扫描数据文件
            file_list = self._scan_data_files()
            result.total_files = len(file_list)
            
            if result.total_files == 0:
                self._log("⚠️ 未找到数据文件")
                return result
            
            print(f"\n📂 找到 {result.total_files} 个数据文件")
            
            # 2. 批量解析和分析
            processing_results = self._batch_analyze_files(file_list)
            result.processing_results = processing_results
            result.processed_files = len(processing_results)
            result.successful_files = sum(1 for r in processing_results if r.success)
            result.failed_files = result.processed_files - result.successful_files
            
            print(f"\n📊 处理统计:")
            print(f"   总文件数: {result.total_files}")
            print(f"   处理成功: {result.successful_files}")
            print(f"   处理失败: {result.failed_files}")
            
            # 3. 聚合数据
            aggregated = self._aggregate_results(processing_results)
            result.aggregated_data = aggregated
            
            if result.successful_files == 0:
                self._log("❌ 没有成功处理的文件，无法继续")
                return result
            
            # 4. Arrhenius 分析
            if self.config.enable_arrhenius and self.arrhenius_analyzer:
                print(f"\n🔬 执行多点 Arrhenius 分析...")
                arrhenius_result = self._perform_arrhenius_analysis(aggregated)
                result.arrhenius_result = arrhenius_result
            
            # 5. 保存结果
            self._save_results(result)
            
            # 6. 生成图表（PNG）
            if self.config.enable_reporting:
                print(f"\n📈 生成图表...")
                report_paths = self._generate_reports(result)
                result.report_paths = report_paths
            
            # 7. 完成
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            print(f"\n✅ 批处理完成")
            print(f"   耗时: {result.duration_seconds:.2f} 秒")
            
            return result
        
        except Exception as e:
            self._log(f"❌ 批处理异常: {str(e)}")
            self._log(traceback.format_exc())
            
            result.end_time = datetime.now()
            if result.start_time:
                result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            
            return result
    
    # ========================================================
    # 内部流程：扫描数据文件
    # ========================================================
    
    def _scan_data_files(self) -> List[str]:
        """
        扫描数据目录，查找所有 CHI 数据文件
        
        Returns:
            List[str]: 文件路径列表
        """
        print(f"\n🔍 扫描数据目录: {self.config.data_dir}")
        
        if not os.path.exists(self.config.data_dir):
            self._log(f"❌ 数据目录不存在: {self.config.data_dir}")
            return []
        
        file_list = []
        
        # 使用 pathlib 扫描文件
        data_path = Path(self.config.data_dir)
        
        # 匹配 CHI 文件
        pattern = self.config.chi_file_pattern
        for filepath in data_path.glob(pattern):
            if filepath.is_file():
                file_list.append(str(filepath))
        
        # 按文件名排序
        file_list.sort()
        
        print(f"   找到 {len(file_list)} 个文件")
        
        return file_list
    
    # ========================================================
    # 内部流程：批量分析
    # ========================================================
    
    def _batch_analyze_files(self, file_list: List[str]) -> List[ProcessingResult]:
        """
        批量解析和分析文件
        
        Args:
            file_list: 文件路径列表
        
        Returns:
            List[ProcessingResult]: 处理结果列表
        """
        print(f"\n🔄 批量分析文件...")
        
        results = []
        
        for i, filepath in enumerate(file_list, 1):
            print(f"\n[{i}/{len(file_list)}] 处理: {os.path.basename(filepath)}")
            
            result = self._process_single_file(filepath)
            results.append(result)
            
            if result.success:
                print(f"   ✅ 成功 (T={result.temperature_C}°C)")
            else:
                print(f"   ❌ 失败: {result.error}")
                
                if not self.config.continue_on_error:
                    self._log(f"⚠️ 遇到错误，停止批处理")
                    break
        
        return results
    
    def _process_single_file(self, filepath: str) -> ProcessingResult:
        """
        处理单个文件（解析 + 分析）
        
        Args:
            filepath: 文件路径
        
        Returns:
            ProcessingResult: 处理结果
        """
        try:
            # 1. 解析文件
            parse_result = self._parse_chi_file(filepath)
            
            if not parse_result['success']:
                return ProcessingResult(
                    filepath=filepath,
                    success=False,
                    error=f"解析失败: {parse_result.get('error')}"
                )
            
            # 2. 提取温度
            temperature_C = self._extract_temperature_from_filename(filepath)
            
            if temperature_C is None:
                return ProcessingResult(
                    filepath=filepath,
                    success=False,
                    error="无法从文件名提取温度"
                )
            
            # 3. EIS 分析
            if self.eis_analyzer:
                analysis_result = self.eis_analyzer(
                    frequencies=parse_result['frequencies'],
                    z_real=parse_result['z_real'],
                    z_imag=parse_result['z_imag'],
                    temperature_K=temperature_C + 273.15,
                    thickness_cm=self.config.thickness_cm,
                    area_cm2=self.config.area_cm2,
                )
            else:
                # 无分析器，返回原始数据
                analysis_result = {
                    'success': True,
                    'raw_data': {
                        'frequencies': parse_result['frequencies'],
                        'z_real': parse_result['z_real'],
                        'z_imag': parse_result['z_imag'],
                    }
                }
            
            # 4. 构建结果
            return ProcessingResult(
                filepath=filepath,
                success=True,
                temperature_C=temperature_C,
                data={
                    'raw': parse_result,
                    'analysis': analysis_result,
                }
            )
        
        except Exception as e:
            error_msg = f"处理异常: {str(e)}"
            self._log(f"❌ {filepath}: {error_msg}")
            self._log(traceback.format_exc())
            
            return ProcessingResult(
                filepath=filepath,
                success=False,
                error=error_msg
            )
    
    # ========================================================
    # 内部流程：解析文件
    # ========================================================
    
    def _parse_chi_file(self, filepath: str) -> Dict[str, Any]:
        """
        解析 CHI 数据文件
        
        Args:
            filepath: 文件路径
        
        Returns:
            dict: 解析结果
                - success: bool
                - frequencies: array
                - z_real: array
                - z_imag: array
                - error: str
        """
        try:
            # 使用重构的 chi_parser
            from modules.io_utils import chi_parser
            
            result = chi_parser.parse_chi_file(filepath)
            
            if result['success']:
                # 验证数据点数
                n_points = len(result['frequencies'])
                if n_points < 10:
                    return {
                        'success': False,
                        'error': f'数据点数不足: {n_points} < 10'
                    }
            
            return result
        
        except Exception as e:
            return {
                'success': False,
                'error': f'解析异常: {str(e)}'
            }
    
    def _extract_temperature_from_filename(self, filepath: str) -> Optional[float]:
        """
        从文件名提取温度（鲁棒版）
        
        支持的文件名格式：
        - Material_T25.0_f0.1_1000000_V0.txt
        - Material_T-10.0_f0.1_1000000_V0.txt
        - Sample_T15.0_f0.1_1000000_V0_#1.txt  (带序号)
        - LLZO_T25C_...txt  (带 C 后缀)
        - T25_data.txt  (简单格式)
        
        Args:
            filepath: 文件路径
        
        Returns:
            float or None: 温度 (°C)
        """
        import re
        
        filename = os.path.basename(filepath)
        
        # 策略 1: 匹配 _T<数字>_ 或 _T<数字>. 格式（最严格）
        # 例如：Material_T25.0_f0.1 或 Sample_T-10.5_data.txt
        pattern1 = r'_T([-+]?\d+(?:\.\d+)?)(?:_|\.)'
        match = re.search(pattern1, filename, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        # 策略 2: 匹配 _T<数字>C_ 或 _T<数字>C. 格式（带摄氏度符号）
        # 例如：LLZO_T25C_data.txt
        pattern2 = r'_T([-+]?\d+(?:\.\d+)?)C(?:_|\.)'
        match = re.search(pattern2, filename, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        # 策略 3: 匹配开头 T<数字>_ 或 T<数字>. 格式（文件名以 T 开头）
        # 例如：T25_data.txt
        pattern3 = r'^T([-+]?\d+(?:\.\d+)?)(?:_|\.)'
        match = re.search(pattern3, filename, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        
        # 策略 4: 宽松匹配 T<数字> 格式（作为兜底）
        # 例如：MaterialT25f0.1.txt（紧凑格式，无分隔符）
        pattern4 = r'T([-+]?\d+(?:\.\d+)?)'
        match = re.search(pattern4, filename, re.IGNORECASE)
        if match:
            try:
                temp = float(match.group(1))
                # 合理性检查：温度应该在 -200 到 200 °C 范围内
                if -200 <= temp <= 200:
                    return temp
            except ValueError:
                pass
        
        # 无法提取温度
        return None
    
    # ========================================================
    # 内部流程：聚合结果
    # ========================================================
    
    def _aggregate_results(self, processing_results: List[ProcessingResult]) -> Dict[str, Any]:
        """
        聚合处理结果
        
        Args:
            processing_results: 处理结果列表
        
        Returns:
            dict: 聚合数据
                - measurements: List[dict]
                - temperatures_K: array
                - conductivities: array
                - rb_values: array
                - rejected_by_qa: int（QA 熔断数量）
                - kk_warnings: int（KK 警告数量）
        """
        print(f"\n📊 聚合处理结果...")
        
        measurements = []
        temperatures_K = []
        conductivities = []
        rb_values = []
        rejected_by_qa = 0
        kk_warnings = 0  # 改名：从熔断改为警告
        
        for result in processing_results:
            # ===== 处理所有记录（包括失败的） =====
            if result.data and 'analysis' in result.data:
                analysis = result.data['analysis']
                
                # 提取关键数据
                temp_K = result.temperature_C + 273.15
                status = analysis.get('status', 'UNKNOWN')
                kk_warning = analysis.get('kk_warning', False)  # 新增：提取 KK 警告标记

                # Tier2 (2026-06-01): 透传数值 KK 残差，而不仅仅是 bool。
                # validate_kk_consistency 已算出 mu_median/mu_rmse/score 等核心指标，
                # 这里把它们落进 measurement 记录，使下游 result_bundle 能写出
                # 真实数值 kk_residual（旧 pipeline 只写 kk_warning bool，见 issue 10）。
                kk_result = analysis.get('kk_result') or {}
                kk_details = kk_result.get('details') or {}
                kk_mu_median = kk_result.get('mu_median')
                kk_mu_rmse = kk_result.get('mu_rmse')
                kk_mu_max = kk_result.get('mu_max')
                kk_score = kk_result.get('score')
                kk_passed = kk_result.get('passed')
                kk_threshold = kk_details.get('threshold')
                kk_method = kk_result.get('method')

                # 从 rb_result 中提取数据
                rb_result = analysis.get('rb_result', {})
                rb = rb_result.get('rb_ohm') if rb_result else None
                conductivity = rb_result.get('conductivity_s_per_cm') if rb_result else None
                rb_method = rb_result.get('method') if rb_result else None
                fit_quality = rb_result.get('fit_quality') if rb_result else None
                
                # 构建测量记录（包含 status 和 kk_warning）
                measurement = {
                    'filepath': result.filepath,
                    'temperature_C': result.temperature_C,
                    'temperature_K': temp_K,
                    'status': status,
                    'kk_warning': kk_warning,  # 新增：KK 警告标记
                    # Tier2: 数值 KK 残差（核心判定指标 mu_median + 辅助统计）
                    'kk_mu_median': kk_mu_median,
                    'kk_mu_rmse': kk_mu_rmse,
                    'kk_mu_max': kk_mu_max,
                    'kk_score': kk_score,
                    'kk_passed': kk_passed,
                    'kk_threshold': kk_threshold,
                    'kk_method': kk_method,
                    'rb_ohm': rb,
                    'conductivity_S_per_cm': conductivity,
                    'rb_method': rb_method,
                    'fit_quality': fit_quality,
                    'success': analysis.get('success', False),
                    'failure_reason': analysis.get('error') if not analysis.get('success') else None,
                }
                
                measurements.append(measurement)
                
                # 统计熔断和警告数量
                if status == 'REJECTED_BY_QA':
                    rejected_by_qa += 1
                
                # 统计 KK 警告（不再是熔断）
                if kk_warning:
                    kk_warnings += 1
                
                # 收集有效数组数据（用于 Arrhenius，仅成功记录）
                if result.success and rb is not None and conductivity is not None:
                    temperatures_K.append(temp_K)
                    conductivities.append(conductivity)
                    rb_values.append(rb)
        
        print(f"   总测量记录: {len(measurements)}")
        print(f"   有效记录: {len(temperatures_K)}")
        print(f"   QA 熔断: {rejected_by_qa}")
        print(f"   KK 警告: {kk_warnings}")  # 改名：从熔断改为警告
        
        return {
            'measurements': measurements,
            'temperatures_K': temperatures_K,
            'conductivities': conductivities,
            'rb_values': rb_values,
            'rejected_by_qa': rejected_by_qa,
            'kk_warnings': kk_warnings,  # 改名：从 rejected_by_kk 改为 kk_warnings
        }
    
    # ========================================================
    # 内部流程：Arrhenius 分析
    # ========================================================
    
    def _perform_arrhenius_analysis(self, aggregated: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        执行多点 Arrhenius 分析（v4.0 终极多段解算）
        
        Args:
            aggregated: 聚合数据
        
        Returns:
            dict or None: Arrhenius 分析结果
        """
        temperatures_K = aggregated.get('temperatures_K', [])
        conductivities = aggregated.get('conductivities', [])
        
        if len(temperatures_K) < 5:
            self._log("⚠️ 数据点不足，无法进行 Arrhenius 分析（< 5 点）")
            return None
        
        try:
            # 构建测量记录格式
            measurement_records = []
            for T_K, sigma in zip(temperatures_K, conductivities):
                measurement_records.append({
                    'success': True,
                    'temperature_K': T_K,
                    'conductivity_s_per_cm': sigma
                })
            
            # 调用 Arrhenius 分析器
            print(f"   开始竞争性多模型分析...")
            result = self.arrhenius_analyzer(measurement_records)
            
            if result.get('success'):
                print(f"\n   ✅ Arrhenius 分析完成")
                print(f"      最佳模型: {result.get('best_model_type')}")
                print(f"      段数: {result.get('n_segments', 0)}")
                print(f"      置信度: {result.get('confidence', 0)*100:.1f}%")
                
                # 打印模型概率分布
                print(f"\n   [模型概率分布]")
                model_probs = result.get('model_probabilities', {})
                for model_name, prob in model_probs.items():
                    print(f"      {model_name}: {prob*100:.1f}%")
                
                # 打印相变温度
                transition_temps = result.get('transition_temps_K', [])
                if transition_temps:
                    print(f"\n   [相变温度]")
                    for i, T_K in enumerate(transition_temps, 1):
                        print(f"      Tc{i} = {T_K:.2f} K ({T_K-273.15:.2f}°C)")
                
                # 打印各段活化能
                print(f"\n   [各段活化能]")
                segments = result.get('segments', [])
                for i, seg in enumerate(segments):
                    Ea_kJ_mol = seg.get('Ea_kJ_per_mol')
                    if Ea_kJ_mol is not None:
                        print(f"      段 {i}: Ea = {Ea_kJ_mol:.2f} kJ/mol, 点数 = {seg.get('n_points', 0)}")
                    else:
                        print(f"      段 {i}: Ea = N/A, 点数 = {seg.get('n_points', 0)}")
            else:
                print(f"   ⚠️ Arrhenius 分析失败: {result.get('error')}")
            
            return result
        
        except Exception as e:
            self._log(f"❌ Arrhenius 分析异常: {str(e)}")
            self._log(traceback.format_exc())
            return None
    
    # ========================================================
    # 内部流程：保存结果
    # ========================================================
    
    def _save_results(self, batch_result: BatchResult) -> None:
        """
        保存批处理结果
        
        Args:
            batch_result: 批处理结果
        """
        print(f"\n💾 保存结果...")
        
        # 1. 保存聚合数据（JSON）
        aggregated_path = os.path.join(self.config.output_dir, "aggregated_results.json")
        
        try:
            # 转换 numpy 数组为列表（JSON 序列化）
            aggregated_copy = self._convert_for_json(batch_result.aggregated_data)
            
            with open(aggregated_path, 'w', encoding='utf-8') as f:
                json.dump(aggregated_copy, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ 聚合数据: {aggregated_path}")
        
        except Exception as e:
            self._log(f"⚠️ 保存聚合数据失败: {str(e)}")
        
        # 2. 保存 Arrhenius 结果
        if batch_result.arrhenius_result:
            arrhenius_path = os.path.join(self.config.output_dir, "arrhenius_analysis.json")
            
            try:
                arrhenius_copy = self._convert_for_json(batch_result.arrhenius_result)
                
                with open(arrhenius_path, 'w', encoding='utf-8') as f:
                    json.dump(arrhenius_copy, f, indent=2, ensure_ascii=False)
                
                print(f"   ✅ Arrhenius 结果: {arrhenius_path}")
            
            except Exception as e:
                self._log(f"⚠️ 保存 Arrhenius 结果失败: {str(e)}")
        
        # 3. 保存处理日志
        log_path = os.path.join(self.config.output_dir, "processing_log.txt")
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(f"批处理日志\n")
                f.write(f"=" * 60 + "\n")
                f.write(f"开始时间: {batch_result.start_time}\n")
                f.write(f"结束时间: {batch_result.end_time}\n")
                f.write(f"耗时: {batch_result.duration_seconds:.2f} 秒\n")
                f.write(f"\n总文件数: {batch_result.total_files}\n")
                f.write(f"处理成功: {batch_result.successful_files}\n")
                f.write(f"处理失败: {batch_result.failed_files}\n")
                f.write(f"\n" + "=" * 60 + "\n\n")
                
                # 写入所有日志消息
                for msg in self.log_messages:
                    f.write(msg + "\n")
                
                # 写入失败文件列表
                f.write(f"\n失败文件列表:\n")
                f.write("=" * 60 + "\n")
                for result in batch_result.processing_results:
                    if not result.success:
                        f.write(f"❌ {result.filepath}\n")
                        f.write(f"   错误: {result.error}\n\n")
            
            print(f"   ✅ 处理日志: {log_path}")
        
        except Exception as e:
            self._log(f"⚠️ 保存日志失败: {str(e)}")
    
    def _convert_for_json(self, obj: Any) -> Any:
        """
        转换对象为 JSON 可序列化格式
        
        Args:
            obj: 任意对象
        
        Returns:
            JSON 可序列化对象
        """
        import numpy as np
        
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_for_json(item) for item in obj]
        else:
            return obj
    
    # ========================================================
    # 内部流程：生成报告
    # ========================================================
    
    def _generate_reports(self, batch_result: BatchResult) -> List[str]:
        """
        生成图表（仅 PNG：电导率趋势、Arrhenius），不生成 Markdown。
        
        Args:
            batch_result: 批处理结果
        
        Returns:
            List[str]: 生成的 PNG 文件路径列表
        """
        report_paths: List[str] = []
        
        try:
            import numpy as np
            from modules.reporting import plotter
            
            report_data = {
                'material': self.config.material_name,
                'measurements': batch_result.aggregated_data.get('measurements', []),
                'arrhenius': batch_result.arrhenius_result,
                'statistics': {
                    'total_files': batch_result.total_files,
                    'successful': batch_result.successful_files,
                    'failed': batch_result.failed_files,
                    'duration_seconds': batch_result.duration_seconds,
                }
            }
            
            measurements = report_data.get('measurements', [])
            if not measurements:
                return report_paths
            
            successful_measurements = [
                m for m in measurements
                if m.get('status') == 'OK' and m.get('success') is True
            ]
            if not successful_measurements:
                return report_paths
            
            temps_C = [m['temperature_C'] for m in successful_measurements]
            temps_K = [m['temperature_K'] for m in successful_measurements]
            conds = [m['conductivity_S_per_cm'] for m in successful_measurements]
            
            if not temps_C or not conds:
                return report_paths
            
            output_dir = self.config.output_dir
            
            trend_path = os.path.join(output_dir, "conductivity_trend.png")
            result = plotter.plot_conductivity_trend(
                temperatures_C=np.array(temps_C),
                conductivities_S_cm=np.array(conds),
                output_path=trend_path,
            )
            if result.get('success'):
                report_paths.append(trend_path)
            
            if len(temps_K) >= 3:
                arrhenius_path = os.path.join(output_dir, "arrhenius_plot.png")
                arrhenius_data = report_data.get('arrhenius')
                result = plotter.plot_conductivity_arrhenius(
                    temperatures_K=np.array(temps_K),
                    conductivities_S_cm=np.array(conds),
                    output_path=arrhenius_path,
                    segments=arrhenius_data.get('segments') if arrhenius_data else None,
                    material_name=report_data.get('material', 'Sample'),
                )
                if result.get('success'):
                    report_paths.append(arrhenius_path)
            
            if report_paths:
                print(f"   ✅ 生成图表: {len(report_paths)} 个文件")
                for path in report_paths:
                    print(f"      - {os.path.basename(path)}")
        
        except Exception as e:
            self._log(f"⚠️ 生成图表失败: {str(e)}")
            self._log(traceback.format_exc())
        
        return report_paths
    
    # ========================================================
    # 工具方法
    # ========================================================
    
    def _log(self, message: str) -> None:
        """记录日志消息"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append(log_entry)
        print(log_entry)
    
    def get_log_messages(self) -> List[str]:
        """获取所有日志消息"""
        return self.log_messages.copy()


# ============================================================
# 辅助函数
# ============================================================

def create_default_eis_analyzer():
    """创建默认的 EIS 分析器"""
    try:
        from modules.analysis import eis_pipeline
        
        def analyzer(frequencies, z_real, z_imag, temperature_K, thickness_cm, area_cm2):
            # 注意：eis_pipeline.analyze_eis_point 使用 temperature_C 参数
            temperature_C = temperature_K - 273.15
            return eis_pipeline.analyze_eis_point(
                frequencies=frequencies,
                z_real=z_real,
                z_imag=z_imag,
                temperature_C=temperature_C,
                thickness_cm=thickness_cm,
                area_cm2=area_cm2,
            )
        
        return analyzer
    except ImportError:
        return None


def create_default_arrhenius_analyzer():
    """创建默认的 Arrhenius 分析器（v4.0 终极多段解算）"""
    try:
        from modules.analysis.algorithms.arrhenius import analyze_arrhenius_series
        
        def analyzer(measurement_records):
            """
            Arrhenius 分析器包装函数
            
            Args:
                measurement_records: 测量记录列表，每条包含:
                    - success: bool
                    - temperature_K: float
                    - conductivity_s_per_cm: float
            
            Returns:
                dict: Arrhenius 分析结果
            """
            return analyze_arrhenius_series(
                measurement_records,
                min_points=5,
                min_segment_points=4,
                aic_improvement_threshold=5.0
            )
        
        return analyzer
    except ImportError:
        return None
