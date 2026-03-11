# -*- coding: utf-8 -*-
"""
增强版Phase1数据整合器
充分利用Phase1的所有数据：Arrhenius + DRT + Modulus + 原始EIS
"""
import json
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
import numpy as np


class EnhancedDataIntegrator:
    """增强版数据整合器 - 完整提取Phase1数据"""
    
    def __init__(
        self,
        result_dir: Path = Path("result/batch_optimized"),
        metadata_file: Path = Path("data/材料数据说明.xlsx")
    ):
        """初始化"""
        self.result_dir = Path(result_dir)
        self.metadata_file = Path(metadata_file)
        
        # 加载所有材料类型的元数据
        self.metadata = self._load_metadata()
        
    def _load_metadata(self) -> Dict:
        """加载材料数据说明.xlsx元数据（支持所有材料类型）"""
        try:
            if not self.metadata_file.exists():
                print(f"[WARNING] 元数据文件不存在: {self.metadata_file}")
                return {}
            
            metadata = {}
            xl_file = pd.ExcelFile(self.metadata_file)
            
            # 处理所有sheet（支持所有材料类型）
            for sheet_name in xl_file.sheet_names:
                try:
                    # 读取sheet（不指定header，先读取前几行判断结构）
                    df = pd.read_excel(self.metadata_file, sheet_name=sheet_name, header=None, nrows=3)
                    
                    # 查找header行（通常第2行是列名）
                    header_row = 1  # 默认第2行（索引1）
                    if len(df) > 1:
                        # 检查第2行是否包含"材料成分"或样品ID相关文本
                        row1_text = ' '.join([str(x) for x in df.iloc[1].values if pd.notna(x)])
                        if '材料成分' not in row1_text and '成分' not in row1_text:
                            header_row = 0  # 如果第2行不是header，使用第1行
                    
                    # 重新读取，使用正确的header
                    df = pd.read_excel(self.metadata_file, sheet_name=sheet_name, header=header_row)
                    
                    # 查找样品ID列（通常包含"材料成分"或在第2列）
                    sample_id_col = None
                    for col in df.columns:
                        col_str = str(col)
                        if '材料成分' in col_str or '成分' in col_str:
                            sample_id_col = col
                            break
                    if sample_id_col is None and len(df.columns) > 1:
                        sample_id_col = df.columns[1]  # 默认第2列
                    
                    if sample_id_col is None:
                        print(f"[WARNING] Sheet '{sheet_name}': 未找到样品ID列，跳过")
                        continue
                    
                    # 查找R和N列
                    r_col = None
                    n_col = None
                    for col in df.columns:
                        col_str = str(col).strip()
                        # R列：查找包含"酸水的摩尔比"的列（根据Excel结构，这是R的定义）
                        if '酸水' in col_str and '摩尔比' in col_str and '黏土中水' not in col_str:
                            r_col = col
                            break
                        # 也尝试英文列名
                        elif col_str == 'R' or (len(col_str) == 1 and col_str == 'R'):
                            r_col = col
                            break
                        elif 'ratio' in col_str.lower() and 'a1' in col_str.lower() and 'a2' in col_str.lower():
                            r_col = col
                            break
                    
                    # 如果还没找到R列，尝试通过列索引（根据Excel结构，R在第13列，索引12）
                    if r_col is None and len(df.columns) > 12:
                        potential_r_col = df.columns[12]
                        col_str = str(potential_r_col).strip()
                        if '酸水' in col_str and '摩尔比' in col_str:
                            r_col = potential_r_col
                        else:
                            # 尝试读取值判断
                            try:
                                test_val = df[potential_r_col].dropna().iloc[0] if len(df[potential_r_col].dropna()) > 0 else None
                                if test_val is not None:
                                    test_float = float(test_val)
                                    if 0 <= test_float <= 2.0:  # R的合理范围
                                        r_col = potential_r_col
                            except:
                                pass
                    
                    # 查找N列：查找包含"液体和黏土的重量比"的列（根据Excel结构，这是N的定义）
                    for col in df.columns:
                        col_str = str(col).strip()
                        if '液体' in col_str and '黏土' in col_str and '重量比' in col_str:
                            n_col = col
                            break
                        elif '液固' in col_str or ('liquid' in col_str.lower() and 'solid' in col_str.lower()):
                            n_col = col
                            break
                        elif col_str == 'N' or (len(col_str) == 1 and col_str == 'N'):
                            n_col = col
                            break
                    
                    # 如果还没找到N列，尝试通过列索引（根据Excel结构，N在第21列，索引20）
                    if n_col is None and len(df.columns) > 20:
                        potential_n_col = df.columns[20]
                        col_str = str(potential_n_col).strip()
                        if '液体' in col_str and '黏土' in col_str:
                            n_col = potential_n_col
                    
                    # 提取材料类型（从sheet名称）
                    material_type = sheet_name  # S8, S60, S6等
                    
                    # 处理每一行
                    for _, row in df.iterrows():
                        if sample_id_col not in df.columns:
                            continue
                            
                        sample_id_raw = row[sample_id_col]
                        if pd.isna(sample_id_raw):
                            continue
                        
                        sample_id = str(sample_id_raw).strip()
                        if sample_id == 'nan' or not sample_id.startswith('S'):
                            continue
                        
                        # 提取R值
                        r_value = None
                        if r_col and r_col in df.columns:
                            try:
                                r_raw = row[r_col]
                                if pd.notna(r_raw):
                                    r_value = float(r_raw)
                            except:
                                pass
                        
                        # 提取N值（S60等无黏土的材料可能没有N）
                        n_value = None
                        if n_col and n_col in df.columns:
                            try:
                                n_raw = row[n_col]
                                if pd.notna(n_raw):
                                    n_value = float(n_raw)
                            except:
                                pass
                        
                        # 提取Sepiolite质量（如果有）
                        sepiolite_mg = None
                        for col in df.columns:
                            col_str = str(col).lower()
                            if ('weight' in col_str or 'wight' in col_str) and ('mg' in col_str or '黏土' in col_str or 'sepiolite' in col_str):
                                try:
                                    val = row[col]
                                    if pd.notna(val):
                                        sepiolite_mg = float(val)
                                        break
                                except:
                                    pass
                        
                        # 存储元数据
                        if sample_id not in metadata:  # 避免重复
                            metadata[sample_id] = {
                                'R': r_value,
                                'N': n_value,
                                'sepiolite_mg': sepiolite_mg if sepiolite_mg is not None else (450.0 if material_type == 'S8' else 0),
                                'sample_type': material_type
                            }
                    
                    print(f"[OK] Sheet '{sheet_name}': 加载 {len([k for k in metadata if k.startswith(material_type)])} 个样品")
                    
                except Exception as e:
                    print(f"[WARNING] Sheet '{sheet_name}' 加载失败: {e}")
                    continue
            
            # 统计各材料类型
            type_counts = {}
            for sample_id, meta in metadata.items():
                mat_type = meta.get('sample_type', 'unknown')
                type_counts[mat_type] = type_counts.get(mat_type, 0) + 1
            
            print(f"[OK] 总计加载元数据: {len(metadata)} 个样品")
            for mat_type, count in sorted(type_counts.items()):
                print(f"  {mat_type}: {count} 个")
            
            return metadata
        except Exception as e:
            print(f"[ERROR] 加载元数据失败: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def integrate_sample(self, sample_dir_name: str) -> Dict[str, Any]:
        """
        整合单个样品的完整数据
        
        Args:
            sample_dir_name: Phase1样品目录名（如phase1_S8-3-1-2_300-150K 1K-min）
            
        Returns:
            完整的整合数据字典
        """
        sample_dir = self.result_dir / sample_dir_name
        if not sample_dir.exists():
            return {'error': f'样品目录不存在: {sample_dir_name}'}
        
        # 提取样品ID
        sample_id = self._extract_sample_id(sample_dir_name)
        # 从样品ID提取材料类型（支持所有材料类型）
        sample_type = self._extract_sample_type(sample_id)
        
        # 获取元数据（支持前缀匹配）
        metadata = self.metadata.get(sample_id, {})
        if not metadata:
            # 尝试前缀匹配（如S8-3-1-2 → S8-3-1）
            for meta_id in self.metadata.keys():
                if sample_id.startswith(meta_id):
                    metadata = self.metadata[meta_id]
                    break
        
        integrated_data = {
            'sample_dir_name': sample_dir_name,
            'sample_id': sample_id,
            'sample_type': sample_type,
            'metadata': metadata,
            'phase1_data': {}
        }
        
        # 1. Arrhenius分析（增强版）
        integrated_data['phase1_data']['arrhenius'] = self._load_arrhenius_enhanced(sample_dir)
        
        # 2. DRT分析（完整版 - 关键！）
        integrated_data['phase1_data']['drt'] = self._load_drt_enhanced(sample_dir)
        
        # 3. Modulus分析（完整版 - 关键！）
        integrated_data['phase1_data']['modulus'] = self._load_modulus_enhanced(sample_dir)
        
        # 4. 电导率数据
        integrated_data['phase1_data']['conductivity'] = self._load_conductivity(sample_dir)
        
        # 5. Rb拟合数据
        integrated_data['phase1_data']['rb_fitting'] = self._load_rb_fitting(sample_dir)
        
        # 6. 温度关联数据（关键 - 将Rb/Arrhenius/DRT/Modulus按温度对齐）
        integrated_data['phase1_data']['temperature_correlated'] = self._create_temperature_correlation(
            integrated_data['phase1_data']
        )
        
        # 7. 提取Phase1报告摘要
        integrated_data['phase1_report_summary'] = self._extract_report_summary(sample_dir)
        
        # 8. 加载质量评分（新增，基于已加载的Arrhenius数据）
        integrated_data['phase1_data']['quality'] = self._load_quality_assessment(
            sample_dir, 
            integrated_data['phase1_data'].get('arrhenius', {})
        )
        
        return integrated_data
    
    def _extract_sample_id(self, sample_dir_name: str) -> str:
        """从目录名提取样品ID"""
        import re
        match = re.search(r'phase1_(S\d+-[\d-]+)', sample_dir_name)
        if match:
            return match.group(1)
        return sample_dir_name.split('_')[1] if '_' in sample_dir_name else sample_dir_name
    
    def _extract_sample_type(self, sample_id: str) -> str:
        """从样品ID提取材料类型（支持所有材料类型）"""
        import re
        match = re.match(r'^(S\d+)', sample_id)
        if match:
            return match.group(1)
        return 'unknown'
    
    def _load_arrhenius_enhanced(self, sample_dir: Path) -> Dict:
        """加载增强版Arrhenius数据"""
        arr_file = sample_dir / 'arrhenius' / 'arrhenius_analysis.json'
        
        if not arr_file.exists():
            return {'error': '文件不存在'}
        
        try:
            with open(arr_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取分段信息并应用质量过滤
            segments = []
            for seg in data.get('segments', []):
                # 提取激活能和R2
                ea = seg.get('activation_energy_eV', seg.get('Ea', 0))
                r2 = seg.get('r_squared', 0)
                
                # 质量过滤：R2≥0.9, Ea>0
                if r2 >= 0.9 and ea > 0:
                    segments.append({
                        'segment_id': seg.get('segment', 0),
                        'T_min_K': seg.get('temperature_range', seg.get('T_range', [0, 0]))[0],
                        'T_max_K': seg.get('temperature_range', seg.get('T_range', [0, 0]))[1],
                        'Ea_eV': ea,
                        'Ea_stderr': seg.get('Ea_stderr', seg.get('Ea_error', None)),
                        'Ea_ci_95': seg.get('Ea_ci_95', None),
                        'Ea_ci_lower': seg.get('Ea_ci_lower', None),
                        'Ea_ci_upper': seg.get('Ea_ci_upper', None),
                        'Ea_relative_error': seg.get('Ea_relative_error', None),
                        'sigma0_S_cm': seg.get('sigma0', 0),
                        'sigma0_error': seg.get('sigma0_error', None),
                        'R_squared': r2,
                        'p_value': seg.get('p_value', None),
                        'n_points': seg.get('n_points', seg.get('points', 0)),
                        'quality': seg.get('quality', 'unknown'),
                        'physics_valid': seg.get('physics_valid', True)
                    })
            
            return {
                'n_segments': len(segments),
                'segments': segments,
                'Ea_mean': np.mean([s['Ea_eV'] for s in segments]) if segments else 0,
                'Ea_std': np.std([s['Ea_eV'] for s in segments]) if segments else 0,
                'Ea_range': [min([s['Ea_eV'] for s in segments]) if segments else 0,
                             max([s['Ea_eV'] for s in segments]) if segments else 0]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _load_drt_enhanced(self, sample_dir: Path) -> Dict:
        """加载增强版DRT数据（关键！）
        
        优化：如果DRT被禁用，直接返回空字典，避免不必要的处理
        """
        adv_file = sample_dir / 'advanced_analysis' / 'advanced_analysis_results.json'
        
        if not adv_file.exists():
            # 文件不存在，可能DRT被禁用，返回空字典（而不是error）
            return {}
        
        try:
            with open(adv_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查DRT是否被禁用
            data_source_summary = data.get('data_source_summary', {})
            if data_source_summary.get('drt_enabled', True) == False:
                # DRT被禁用，直接返回空字典
                return {}
            
            drt_data = data.get('drt_analysis', {})
            
            # 如果drt_data为空字典，也直接返回
            if not drt_data or len(drt_data) == 0:
                return {}
            
            # 按温度整理DRT峰
            drt_by_temp = {}
            for temp_str, temp_data in drt_data.items():
                try:
                    temp_K = float(temp_str)
                except:
                    continue
                
                peaks = temp_data.get('peaks', [])
                
                peaks_info = []
                for peak in peaks:
                    tau_s = peak.get('tau', 0)
                    freq_Hz = 1 / (2 * np.pi * tau_s) if tau_s > 0 else 0
                    
                    peaks_info.append({
                        'tau_s': tau_s,
                        'frequency_Hz': freq_Hz,
                        'gamma_peak': peak.get('gamma', 0),
                        'prominence': peak.get('prominence', 0),
                        'confidence': peak.get('confidence', 0)
                    })
                
                drt_by_temp[temp_K] = {
                    'n_peaks': len(peaks_info),
                    'peaks': peaks_info,
                    'main_peak': peaks_info[0] if peaks_info else None
                }
            
            # 统计信息
            all_peaks = []
            for temp_data in drt_by_temp.values():
                all_peaks.extend(temp_data['peaks'])
            
            # 主峰频率范围
            main_freqs = []
            for temp_data in drt_by_temp.values():
                if temp_data['main_peak']:
                    main_freqs.append(temp_data['main_peak']['frequency_Hz'])
            
            return {
                'n_temperatures': len(drt_by_temp),
                'total_peaks': len(all_peaks),
                'temps_with_peaks': sum(1 for td in drt_by_temp.values() if td['n_peaks'] > 0),
                'peak_detection_rate': sum(1 for td in drt_by_temp.values() if td['n_peaks'] > 0) / len(drt_by_temp) if drt_by_temp else 0,
                'main_frequency_range_Hz': [min(main_freqs), max(main_freqs)] if main_freqs else [0, 0],
                'main_frequency_median_Hz': np.median(main_freqs) if main_freqs else 0,
                'detailed_by_temperature': drt_by_temp
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _load_modulus_enhanced(self, sample_dir: Path) -> Dict:
        """加载增强版Modulus数据（关键！）
        
        优化：如果Modulus被禁用，直接返回空字典，避免不必要的处理
        """
        adv_file = sample_dir / 'advanced_analysis' / 'advanced_analysis_results.json'
        
        if not adv_file.exists():
            # 文件不存在，可能Modulus被禁用，返回空字典（而不是error）
            return {}
        
        try:
            with open(adv_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查Modulus是否被禁用
            data_source_summary = data.get('data_source_summary', {})
            if data_source_summary.get('modulus_enabled', True) == False:
                # Modulus被禁用，直接返回空字典
                return {}
            
            modulus_data = data.get('modulus', {})
            
            # 如果modulus_data为空字典，也直接返回
            if not modulus_data or len(modulus_data) == 0:
                return {}
            
            # 按温度整理Modulus峰
            modulus_by_temp = {}
            for temp_str, temp_data in modulus_data.items():
                try:
                    temp_K = float(temp_str)
                except:
                    continue
                
                peaks = temp_data.get('peaks', [])
                
                peaks_info = []
                for peak in peaks:
                    freq_Hz = peak.get('freq_peak', 0)
                    tau_s = 1 / (2 * np.pi * freq_Hz) if freq_Hz > 0 else 0
                    
                    peaks_info.append({
                        'frequency_Hz': freq_Hz,
                        'tau_s': tau_s,
                        'M_double_prime_peak': peak.get('M_imag_peak', 0),
                        'prominence': peak.get('prominence', 0)
                    })
                
                modulus_by_temp[temp_K] = {
                    'n_peaks': len(peaks_info),
                    'peaks': peaks_info,
                    'epsilon_r': temp_data.get('epsilon_r_used', 1.0),
                    'main_peak': peaks_info[0] if peaks_info else None
                }
            
            # 统计信息
            main_freqs = []
            for temp_data in modulus_by_temp.values():
                if temp_data['main_peak']:
                    main_freqs.append(temp_data['main_peak']['frequency_Hz'])
            
            return {
                'n_temperatures': len(modulus_by_temp),
                'temps_with_peaks': sum(1 for td in modulus_by_temp.values() if td['n_peaks'] > 0),
                'coverage_rate': sum(1 for td in modulus_by_temp.values() if td['n_peaks'] > 0) / len(modulus_by_temp) if modulus_by_temp else 0,
                'main_frequency_range_Hz': [min(main_freqs), max(main_freqs)] if main_freqs else [0, 0],
                'main_frequency_median_Hz': np.median(main_freqs) if main_freqs else 0,
                'detailed_by_temperature': modulus_by_temp
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _load_conductivity(self, sample_dir: Path) -> Dict:
        """加载电导率数据"""
        cond_file = sample_dir / 'conductivity' / 'conductivity_data.csv'
        
        if not cond_file.exists():
            return {'error': '文件不存在'}
        
        try:
            df = pd.read_csv(cond_file)
            
            return {
                'n_points': len(df),
                'T_range_K': [df['Temperature_K'].min(), df['Temperature_K'].max()],
                'sigma_range_S_cm': [df['Conductivity_S_cm'].min(), df['Conductivity_S_cm'].max()],
                'dynamic_range': df['Conductivity_S_cm'].max() / df['Conductivity_S_cm'].min() if df['Conductivity_S_cm'].min() > 0 else 0,
                'data': df[['Temperature_K', 'Conductivity_S_cm']].to_dict('records')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _load_rb_fitting(self, sample_dir: Path) -> Dict:
        """加载Rb拟合数据"""
        rb_file = sample_dir / 'impedance_fitting' / 'rb_fitting_results.csv'
        
        if not rb_file.exists():
            return {'error': '文件不存在'}
        
        try:
            df = pd.read_csv(rb_file)
            
            return {
                'n_points': len(df),
                'T_range_K': [df['Temperature_K'].min(), df['Temperature_K'].max()],
                'Rb_range_Ohm': [df['Rb_Ohm'].min(), df['Rb_Ohm'].max()],
                'avg_R_squared': df['R_squared'].mean(),
                'high_quality_ratio': (df['R_squared'] > 0.95).sum() / len(df),
                'data': df[['Temperature_K', 'Rb_Ohm', 'R_squared']].to_dict('records')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _create_temperature_correlation(self, phase1_data: Dict) -> Dict:
        """创建温度关联数据（关键 - 将所有数据按温度对齐）"""
        
        # 获取所有温度点
        all_temps = set()
        
        # 从Rb获取温度
        if 'rb_fitting' in phase1_data and 'data' in phase1_data['rb_fitting']:
            for point in phase1_data['rb_fitting']['data']:
                all_temps.add(point['Temperature_K'])
        
        # 从DRT获取温度
        if 'drt' in phase1_data and 'detailed_by_temperature' in phase1_data['drt']:
            all_temps.update(phase1_data['drt']['detailed_by_temperature'].keys())
        
        # 从Modulus获取温度
        if 'modulus' in phase1_data and 'detailed_by_temperature' in phase1_data['modulus']:
            all_temps.update(phase1_data['modulus']['detailed_by_temperature'].keys())
        
        # 按温度整理
        correlated_data = {}
        for temp in sorted(all_temps):
            temp_data = {'temperature_K': temp}
            
            # Rb/电导率
            if 'rb_fitting' in phase1_data and 'data' in phase1_data['rb_fitting']:
                rb_points = [p for p in phase1_data['rb_fitting']['data'] 
                           if abs(p['Temperature_K'] - temp) < 0.5]
                if rb_points:
                    temp_data['Rb_Ohm'] = rb_points[0]['Rb_Ohm']
                    temp_data['Rb_R_squared'] = rb_points[0]['R_squared']
            
            if 'conductivity' in phase1_data and 'data' in phase1_data['conductivity']:
                cond_points = [p for p in phase1_data['conductivity']['data']
                             if abs(p['Temperature_K'] - temp) < 0.5]
                if cond_points:
                    temp_data['sigma_S_cm'] = cond_points[0]['Conductivity_S_cm']
            
            # Arrhenius分段
            if 'arrhenius' in phase1_data and 'segments' in phase1_data['arrhenius']:
                for seg in phase1_data['arrhenius']['segments']:
                    if seg['T_min_K'] <= temp <= seg['T_max_K']:
                        temp_data['arrhenius_segment'] = seg['segment_id']
                        temp_data['Ea_eV'] = seg['Ea_eV']
                        break
            
            # DRT峰
            if 'drt' in phase1_data and 'detailed_by_temperature' in phase1_data['drt']:
                if temp in phase1_data['drt']['detailed_by_temperature']:
                    drt_temp = phase1_data['drt']['detailed_by_temperature'][temp]
                    temp_data['drt_n_peaks'] = drt_temp['n_peaks']
                    if drt_temp['main_peak']:
                        temp_data['drt_main_freq_Hz'] = drt_temp['main_peak']['frequency_Hz']
                        temp_data['drt_main_tau_s'] = drt_temp['main_peak']['tau_s']
            
            # Modulus峰
            if 'modulus' in phase1_data and 'detailed_by_temperature' in phase1_data['modulus']:
                if temp in phase1_data['modulus']['detailed_by_temperature']:
                    mod_temp = phase1_data['modulus']['detailed_by_temperature'][temp]
                    temp_data['modulus_n_peaks'] = mod_temp['n_peaks']
                    if mod_temp['main_peak']:
                        temp_data['modulus_main_freq_Hz'] = mod_temp['main_peak']['frequency_Hz']
                        temp_data['modulus_epsilon_r'] = mod_temp['epsilon_r']
            
            correlated_data[temp] = temp_data
        
        return correlated_data
    
    def _extract_report_summary(self, sample_dir: Path) -> Dict:
        """提取Phase1报告摘要（完整文本）"""
        report_file = sample_dir / 'reports' / 'phase1_analysis_report.md'
        
        if not report_file.exists():
            return {'error': '文件不存在', 'content': ''}
        
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                'report_exists': True,
                'full_content': content,  # 返回完整报告
                'content_length': len(content)
            }
        except Exception as e:
            return {'error': str(e), 'content': ''}
    
    def _load_quality_assessment(self, sample_dir: Path, arrhenius_data: Dict) -> Dict:
        """加载质量评分数据"""
        # 尝试多个可能的位置
        quality_files = [
            sample_dir / 'quality_assessment.json',
            sample_dir / 'analysis_summary.json',
            sample_dir / 'quality' / 'quality_assessment.json'
        ]
        
        for quality_file in quality_files:
            if quality_file.exists():
                try:
                    with open(quality_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 提取质量评分（支持多种格式）
                    quality_score = data.get('quality_score') or data.get('quality', {}).get('quality_score', 0)
                    quality_level = data.get('quality_level') or data.get('quality', {}).get('quality_level', 'unknown')
                    use_for_modeling = data.get('use_for_modeling') or data.get('quality', {}).get('use_for_modeling', False)
                    
                    return {
                        'quality_score': float(quality_score) if quality_score is not None else 0,
                        'quality_level': quality_level,
                        'use_for_modeling': use_for_modeling
                    }
                except Exception as e:
                    continue
        
        # 如果找不到质量评分文件，从Arrhenius数据计算
        segments = arrhenius_data.get('segments', [])
        
        if segments:
            # 计算平均R²作为质量指标
            r2_values = [seg.get('R_squared', 0) for seg in segments]
            avg_r2 = np.mean(r2_values) if r2_values else 0
            
            # 根据R²估算质量评分
            if avg_r2 >= 0.99:
                quality_score = 95
                quality_level = 'excellent'
            elif avg_r2 >= 0.95:
                quality_score = 85
                quality_level = 'good'
            elif avg_r2 >= 0.90:
                quality_score = 75
                quality_level = 'acceptable'
            else:
                quality_score = 60
                quality_level = 'poor'
            
            return {
                'quality_score': quality_score,
                'quality_level': quality_level,
                'use_for_modeling': quality_score >= 70
            }
        
        return {
            'quality_score': 0,
            'quality_level': 'unknown',
            'use_for_modeling': False
        }


def test_enhanced_integrator():
    """测试增强版整合器"""
    integrator = EnhancedDataIntegrator()
    
    # 测试一个样品
    test_sample = 'phase1_S8-3-1-2_300-150K 1K-min'
    
    print(f"\n测试样品: {test_sample}")
    print("="*80)
    
    data = integrator.integrate_sample(test_sample)
    
    if 'error' in data:
        print(f"[ERROR] {data['error']}")
        return
    
    print(f"\n样品ID: {data['sample_id']}")
    print(f"样品类型: {data['sample_type']}")
    print("\n元数据:")
    for key, value in data['metadata'].items():
        print(f"  {key}: {value}")
    
    print("\nPhase1数据:")
    
    # Arrhenius
    arr = data['phase1_data']['arrhenius']
    print(f"\n  Arrhenius分段数: {arr.get('n_segments', 0)}")
    if 'segments' in arr:
        for seg in arr['segments']:
            print(f"    分段{seg['segment_id']}: Ea={seg['Ea_eV']:.3f} eV, "
                  f"T={seg['T_min_K']:.0f}-{seg['T_max_K']:.0f} K, R2={seg['R_squared']:.4f}")
    
    # DRT
    drt = data['phase1_data']['drt']
    print(f"\n  DRT分析:")
    print(f"    温度点数: {drt.get('n_temperatures', 0)}")
    print(f"    总峰数: {drt.get('total_peaks', 0)}")
    print(f"    峰检测率: {drt.get('peak_detection_rate', 0)*100:.1f}%")
    if 'main_frequency_range_Hz' in drt:
        freq_range = drt['main_frequency_range_Hz']
        print(f"    主峰频率范围: {freq_range[0]:.1f} - {freq_range[1]:.1f} Hz")
        print(f"    主峰频率中位数: {drt.get('main_frequency_median_Hz', 0):.1f} Hz")
    
    # Modulus
    mod = data['phase1_data']['modulus']
    print(f"\n  Modulus分析:")
    print(f"    温度点数: {mod.get('n_temperatures', 0)}")
    print(f"    覆盖率: {mod.get('coverage_rate', 0)*100:.1f}%")
    if 'main_frequency_range_Hz' in mod:
        freq_range = mod['main_frequency_range_Hz']
        print(f"    主峰频率范围: {freq_range[0]:.1f} - {freq_range[1]:.1f} Hz")
        print(f"    主峰频率中位数: {mod.get('main_frequency_median_Hz', 0):.1f} Hz")
    
    # 温度关联数据
    temp_corr = data['phase1_data']['temperature_correlated']
    print(f"\n  温度关联数据点: {len(temp_corr)}")
    
    # 显示几个样例温度点
    sample_temps = sorted(temp_corr.keys())[:3]
    for temp in sample_temps:
        td = temp_corr[temp]
        print(f"\n    T={temp:.1f} K:")
        if 'sigma_S_cm' in td:
            print(f"      σ = {td['sigma_S_cm']:.2e} S/cm")
        if 'Ea_eV' in td:
            print(f"      Ea = {td['Ea_eV']:.3f} eV (分段{td.get('arrhenius_segment', '?')})")
        if 'drt_main_freq_Hz' in td:
            print(f"      DRT主峰: {td['drt_main_freq_Hz']:.1f} Hz")
        if 'modulus_main_freq_Hz' in td:
            print(f"      Modulus主峰: {td['modulus_main_freq_Hz']:.1f} Hz")
    
    print("\n" + "="*80)
    print("[OK] 测试完成")


if __name__ == '__main__':
    test_enhanced_integrator()

