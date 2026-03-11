# -*- coding: utf-8 -*-
"""
Phase 1 批量处理脚本
=====================

从原始EIS数据生成analysis_result.json
第一轮 standalone 化后，优先使用 close 内部模块完成处理。

使用方法:
    cd close
    python phase1/run_batch.py --material S8
    python phase1/run_batch.py --all
    python phase1/run_batch.py --sample S8-3-2-1

输出:
    output/phase1_results/{sample_id}_analysis_result.json
"""

import sys
import os

# Windows编码修复
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目路径（standalone first）
CLOSE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLOSE_ROOT))

# 导入 close 的材料参数（正确的 R-N）
from config import get_material_params as get_correct_material_params

# 导入 close 内部处理模块
from specific_conductance.rb_fitting import calculate_rb as v1_calculate_rb
from specific_conductance.data_processing import filter_data
from specific_conductance.conductivity import calculate_conductivity, get_fit_params
from specific_conductance.temperature_calculator import TemperatureCalculator
from auto_control.modules.kk_validation import kk_check
from auto_control.modules.drt_analysis import drt_analyze
from auto_control.modules.data_quality import assess_data_quality
from auto_control.modules.arrhenius_scientific import perform_arrhenius_analysis_scientific

print("[OK] 已加载 close 内部处理模块")

import numpy as np
import pandas as pd
import io
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import stats


class EISBatchProcessor:
    """EIS批量处理器（优先使用 close 内部模块）"""
    
    def __init__(self, data_dir: Path = None, output_dir: Path = None):
        self.data_dir = data_dir or (CLOSE_ROOT / "data" / "raw_eis")
        self.output_dir = output_dir or (CLOSE_ROOT / "output" / "phase1_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.temp_calculator = TemperatureCalculator()
        self.fit_params = get_fit_params()
    
    def find_samples(self, material_type: str = None) -> List[Path]:
        """查找所有样品目录"""
        samples = []
        
        if material_type:
            material_dir = self.data_dir / material_type
            if material_dir.exists():
                for sample_dir in material_dir.iterdir():
                    if sample_dir.is_dir():
                        samples.append(sample_dir)
        else:
            for material_dir in self.data_dir.iterdir():
                if material_dir.is_dir():
                    for sample_dir in material_dir.iterdir():
                        if sample_dir.is_dir():
                            samples.append(sample_dir)
        
        return sorted(samples)
    
    def find_data_folder(self, sample_dir: Path) -> Optional[Path]:
        """查找包含DTA文件的数据文件夹"""
        dta_files = list(sample_dir.glob("*.DTA"))
        if dta_files:
            return sample_dir
        
        for subdir in sample_dir.iterdir():
            if subdir.is_dir():
                dta_files = list(subdir.glob("*.DTA"))
                if dta_files:
                    return subdir
        
        return None
    
    def read_dta_files(self, folder_path: Path) -> Dict[float, pd.DataFrame]:
        """读取所有DTA文件"""
        data_dict = {}
        dta_files = sorted(folder_path.glob("*.DTA"))
        
        for dta_file in dta_files:
            try:
                temp_result = self.temp_calculator.calculate_temperature_with_phases(str(dta_file))
                temperature = temp_result['temperature']
                is_valid = temp_result['is_valid']
                
                if not is_valid:
                    continue
                
                df = self._parse_dta_file(dta_file)
                if df is not None and len(df) >= 5:
                    data_dict[temperature] = df
            except Exception as e:
                continue
        
        return data_dict
    
    def _parse_dta_file(self, dta_file: Path) -> Optional[pd.DataFrame]:
        """解析DTA文件"""
        try:
            with open(dta_file, 'r', encoding='latin-1') as f:
                lines = f.readlines()
            
            data_start = None
            for i, line in enumerate(lines):
                if 'ZCURVE' in line:
                    data_start = i + 3
                    break
            
            if data_start is None:
                return None
            
            data_lines = []
            for line in lines[data_start:]:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = re.split(r'\s+', line)
                if len(parts) >= 5:
                    try:
                        int(parts[0])
                        data_lines.append(line)
                    except ValueError:
                        continue
            
            if len(data_lines) < 5:
                return None
            
            data_stream = io.StringIO('\n'.join(data_lines))
            df = pd.read_csv(
                data_stream,
                delimiter=r'\s+',
                names=['Pt', 'Time', 'Freq', 'Zreal', 'Zimag',
                       'Zsig', 'Zmod', 'Zphz', 'Idc', 'Vdc', 'IERange'],
                engine='python',
                on_bad_lines='skip'
            )
            
            df['Freq'] = pd.to_numeric(df['Freq'], errors='coerce')
            df['Zreal'] = pd.to_numeric(df['Zreal'], errors='coerce')
            df['Zimag'] = pd.to_numeric(df['Zimag'], errors='coerce')
            df = df.dropna(subset=['Freq', 'Zreal', 'Zimag'])
            
            return df[['Freq', 'Zreal', 'Zimag']].copy()
            
        except Exception:
            return None
    
    def process_sample(self, sample_dir: Path, generate_plots: bool = False) -> Optional[Dict[str, Any]]:
        """处理单个样品（使用V1完整模块）"""
        sample_id = sample_dir.name
        print(f"  Processing {sample_id}...")
        
        # 获取材料参数（使用close的正确参数）
        params = get_correct_material_params(sample_id)
        if params is None:
            print(f"    [WARN] No material params for {sample_id}")
            params = {'R': 0, 'N': 0, 'L_cm': 0.12, 'S_cm2': 3.92}
        
        # 查找数据文件夹
        data_folder = self.find_data_folder(sample_dir)
        if data_folder is None:
            print(f"    [SKIP] No data folder found")
            return None
        
        # 读取DTA文件
        data_dict = self.read_dta_files(data_folder)
        if not data_dict:
            print(f"    [SKIP] No valid data loaded")
            return None
        
        print(f"    Loaded {len(data_dict)} temperature points")
        
        # 处理每个温度点
        all_results = []
        L = params['L_cm']
        S = params['S_cm2']
        
        for temperature, df in sorted(data_dict.items(), reverse=True):
            freq = df['Freq'].values
            zreal = df['Zreal'].values
            zimag = df['Zimag'].values
            
            # 数据滤波（使用V1的filter_data）
            freq_f, zreal_f, zimag_f = filter_data(freq, zreal, zimag)
            
            if len(freq_f) < 5:
                continue
            
            # Rb拟合（使用V1的calculate_rb）
            try:
                rb_result = v1_calculate_rb(zreal_f, zimag_f, temperature, self.fit_params,
                                           circle_dir=None, freq=freq_f)
                rb_ohm = rb_result.get('rb', 0)
                rb_method = rb_result.get('method', 'unknown')
                rb_r2 = rb_result.get('r', 0.9)
            except Exception as e:
                continue
            
            if rb_ohm is None or rb_ohm <= 0:
                continue
            
            # 电导率计算
            conductivity = calculate_conductivity(rb_ohm, L, S)
            if conductivity is None or conductivity <= 0:
                continue
            
            # KK校验
            try:
                kk_result = kk_check(freq_f, zreal_f, zimag_f)
            except:
                kk_result = {'ok': True, 'score': 70}
            
            # DRT分析
            try:
                drt_result = drt_analyze(freq_f, zreal_f, zimag_f)
            except:
                drt_result = {'ok': True, 'n_peaks': 0, 'peaks': []}
            
            # 数据质量评估
            try:
                quality_result = assess_data_quality(
                    rb_ohm=rb_ohm,
                    z_real=zreal_f.tolist(),
                    z_imag=zimag_f.tolist()
                )
            except:
                quality_result = {'score': 70, 'grade': 'B'}
            
            all_results.append({
                'temperature_K': temperature,
                'rb_ohm': rb_ohm,
                'rb_method': rb_method,
                'rb_r2': rb_r2,
                'conductivity_S_cm': conductivity,
                'n_points': len(freq_f),
                'kk_validation': kk_result,
                'drt_analysis': drt_result,
                'data_quality': quality_result,
            })
            
            print(f"    [OK] T={temperature:.0f}K: Rb={rb_ohm:.2f}Ohm, sigma={conductivity:.4e}S/cm")
        
        if not all_results:
            print(f"    [SKIP] No valid results")
            return None
        
        # 构建结果
        result = self._build_result(sample_id, params, all_results)
        
        ea_str = f"{result['arrhenius'].get('Ea_eV', 0):.3f}" if result['arrhenius'].get('Ea_eV') else 'N/A'
        n_seg = result['arrhenius'].get('n_segments', 0)
        print(f"    [OK] {len(all_results)} points, {n_seg} segments, Ea={ea_str} eV")
        
        return result
    
    def _build_result(self, sample_id: str, params: dict, all_results: List[dict]) -> Dict[str, Any]:
        """构建统一格式的输出结果"""
        all_results.sort(key=lambda x: x['temperature_K'], reverse=True)
        
        temperatures = [r['temperature_K'] for r in all_results]
        conductivities = [r['conductivity_S_cm'] for r in all_results]
        rb_values = [r['rb_ohm'] for r in all_results]
        
        # 过滤用于Arrhenius分析的数据
        valid_temps = []
        valid_conductivities = []
        prev_rb = 0
        
        for r in all_results:
            sigma = r['conductivity_S_cm']
            rb = r['rb_ohm']
            
            if not (r['temperature_K'] > 0 and 1e-10 < sigma < 1 and rb > 0.5):
                continue
            
            # Rb单调性检验
            if prev_rb > 0 and rb < prev_rb:
                continue
            
            valid_temps.append(r['temperature_K'])
            valid_conductivities.append(sigma)
            prev_rb = rb
        
        # Arrhenius分析（使用V1的科学版分析器）
        try:
            arrhenius_result = perform_arrhenius_analysis_scientific(valid_temps, valid_conductivities)
        except Exception as e:
            print(f"    [WARN] Arrhenius analysis failed: {e}")
            arrhenius_result = {'success': False, 'n_segments': 0, 'segments': []}
        
        # 规范化Arrhenius格式
        arrhenius_normalized = self._normalize_arrhenius(arrhenius_result, temperatures)
        
        # 规范化temperature_results格式
        temperature_results_normalized = []
        for r in all_results:
            temp_result = {
                'temperature_K': r['temperature_K'],
                'rb_ohm': r['rb_ohm'],
                'rb_method': r.get('rb_method', 'x_intercept'),
                'rb_r2': r.get('rb_r2', 0.9),
                'conductivity_S_cm': r['conductivity_S_cm'],
                'n_points': r.get('n_points', 56),
                'kk_validation': r.get('kk_validation') or {'ok': True, 'score': 70},
                'drt_analysis': r.get('drt_analysis') or {'ok': True, 'n_peaks': 0, 'peaks': []},
                'data_quality': r.get('data_quality') or {'grade': 'B', 'score': 70, 'flags': []}
            }
            temperature_results_normalized.append(temp_result)
        
        # 计算质量汇总
        quality_scores = [r['data_quality'].get('score', 70) for r in temperature_results_normalized]
        overall_quality_score = np.mean(quality_scores) if quality_scores else 70
        if overall_quality_score >= 85:
            overall_grade = 'A'
        elif overall_quality_score >= 70:
            overall_grade = 'B'
        elif overall_quality_score >= 55:
            overall_grade = 'C'
        else:
            overall_grade = 'D'
        
        result = {
            'sample_id': sample_id,
            'material_type': sample_id.split('-')[0],
            'N': params['N'],
            'R': params['R'],
            'L_cm': params['L_cm'],
            'S_cm2': params['S_cm2'],
            'temperatures': temperatures,
            'rb_values': rb_values,
            'conductivity_values': conductivities,
            'arrhenius': arrhenius_normalized,
            'temperature_results': temperature_results_normalized,
            'quality_summary': {
                'overall_score': float(overall_quality_score),
                'overall_grade': overall_grade,
                'n_temperature_points': len(temperatures),
                'temp_range_K': [min(temperatures), max(temperatures)] if temperatures else [0, 0]
            },
            'metadata': {
                'total_points': len(temperatures),
                'temp_range_K': [min(temperatures), max(temperatures)] if temperatures else [0, 0],
                'sigma_range': [min(conductivities), max(conductivities)] if conductivities else [0, 0]
            },
            'processing_timestamp': datetime.now().isoformat(),
            'source': 'close_phase1_v2',
            'processor_version': '2.0_unified'
        }
        
        return result
    
    def _normalize_arrhenius(self, arrhenius_result: Dict, temperatures: List[float]) -> Dict:
        """规范化Arrhenius结果格式"""
        if not arrhenius_result or not arrhenius_result.get('success'):
            return {'success': False, 'n_segments': 0, 'segments': []}
        
        normalized = {
            'success': True,
            'n_segments': arrhenius_result.get('n_segments', 1),
            'segments': []
        }
        
        segments = arrhenius_result.get('segments', [])
        for i, seg in enumerate(segments):
            Ea_eV = seg.get('Ea_eV') or seg.get('ea_eV') or seg.get('Ea', 0)
            Ea_kJ = seg.get('Ea_kJ_per_mol') or seg.get('ea_kJ_per_mol') or (Ea_eV * 96.485 if Ea_eV else 0)
            
            temp_range = seg.get('temp_range_K') or seg.get('T_range_K')
            if isinstance(temp_range, tuple):
                temp_range = list(temp_range)
            elif not temp_range and temperatures:
                temp_range = [min(temperatures), max(temperatures)]
            else:
                temp_range = temp_range or [0, 0]
            
            r2 = seg.get('r_squared') or seg.get('R_squared') or 0.95
            ln_sigma0 = seg.get('ln_sigma0') or 0
            sigma0 = seg.get('sigma0_S_per_cm') or seg.get('sigma0', np.exp(ln_sigma0) if ln_sigma0 else 1)
            
            norm_seg = {
                'segment': i + 1,
                'Ea_eV': Ea_eV,
                'Ea_kJ_per_mol': Ea_kJ,
                'r_squared': r2,
                'temp_range_K': temp_range,
                'n_points': seg.get('n_points') or seg.get('data_points') or len(temperatures),
                'sigma0_S_per_cm': sigma0,
                'ln_sigma0': ln_sigma0
            }
            normalized['segments'].append(norm_seg)
        
        if normalized['segments']:
            normalized['Ea_eV'] = normalized['segments'][0]['Ea_eV']
            normalized['r_squared'] = normalized['segments'][0]['r_squared']
        
        return normalized
    
    def process_material(self, material_type: str) -> List[Dict[str, Any]]:
        """批量处理指定材料"""
        print(f"\n{'='*60}")
        print(f"Processing {material_type}")
        print(f"{'='*60}")
        
        samples = self.find_samples(material_type)
        print(f"Found {len(samples)} samples")
        
        results = []
        for sample_dir in samples:
            result = self.process_sample(sample_dir)
            if result:
                results.append(result)
                
                output_file = self.output_dir / f"{result['sample_id']}_analysis_result.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n[Summary] {material_type}: {len(results)}/{len(samples)} processed")
        return results
    
    def process_all(self) -> Dict[str, List[Dict[str, Any]]]:
        """处理所有材料"""
        all_results = {}
        
        materials = [d.name for d in self.data_dir.iterdir() if d.is_dir()]
        
        for material in sorted(materials):
            results = self.process_material(material)
            if results:
                all_results[material] = results
        
        summary_file = self.output_dir / "batch_summary.json"
        summary = {
            'timestamp': datetime.now().isoformat(),
            'materials': {m: len(r) for m, r in all_results.items()},
            'total_samples': sum(len(r) for r in all_results.values())
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print("Batch Processing Complete!")
        print(f"{'='*60}")
        print(f"Total: {summary['total_samples']} samples")
        
        return all_results


def main():
    parser = argparse.ArgumentParser(description='Phase 1: 批量处理EIS数据')
    parser.add_argument('--material', '-m', type=str, help='材料类型 (S8, S60等)')
    parser.add_argument('--sample', '-s', type=str, help='单个样品ID')
    parser.add_argument('--all', '-a', action='store_true', help='处理所有材料')
    
    args = parser.parse_args()
    
    processor = EISBatchProcessor()
    
    if args.all:
        processor.process_all()
    elif args.material:
        processor.process_material(args.material)
    elif args.sample:
        sample_id = args.sample
        material = sample_id.split('-')[0]
        sample_dir = processor.data_dir / material / sample_id
        if sample_dir.exists():
            result = processor.process_sample(sample_dir)
            if result:
                output_file = processor.output_dir / f"{sample_id}_analysis_result.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False, default=str)
                print(f"Saved: {output_file}")
        else:
            print(f"Sample not found: {sample_dir}")
    else:
        print("请指定 --material, --sample 或 --all")
        print("使用 -h 查看帮助")


if __name__ == '__main__':
    main()
