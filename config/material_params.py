# -*- coding: utf-8 -*-
"""
材料参数配置
============

从 材料数据说明.xlsx 正确提取的参数

关键定义（与Excel列对应）：
- R: 酸水摩尔比 (Excel列13: "R") = n(H3PO4)/n(H2O)
- N: 液固比 (Excel列21: "液相总量与吸附剂比") = 液相总量/吸附剂质量
- L_cm: 样品厚度 (cm)
- S_cm2: 样品面积 (cm²)

注意：之前的material_config.py把R和N搞反了！这里是修正版
"""

from typing import Dict, Optional
from pathlib import Path
import pandas as pd


def load_material_params_from_excel(excel_path: Path = None) -> Dict[str, Dict]:
    """
    从Excel正确加载材料参数
    
    Returns:
        Dict[sample_id, {R, N, L_cm, S_cm2, material, acid}]
    """
    if excel_path is None:
        excel_path = Path(__file__).parent.parent / "data" / "材料数据说明.xlsx"
    
    all_params = {}
    
    # 定义各材料的列映射
    # Excel结构: 列13是R值, 列21是N值, 列23是L, 列24是S
    
    # 读取S8
    try:
        df_s8 = pd.read_excel(excel_path, sheet_name='S8')
        for idx, row in df_s8.iterrows():
            if idx == 0:  # 跳过表头
                continue
            sample_id = row.iloc[1]  # 第2列是样品ID
            if pd.isna(sample_id) or not str(sample_id).startswith('S8-'):
                continue
            
            R = row.iloc[13]  # 酸水摩尔比
            N = row.iloc[21]  # 液固比
            L = row.iloc[23] if not pd.isna(row.iloc[23]) else 0.12
            S = row.iloc[24] if not pd.isna(row.iloc[24]) else 3.919348
            
            # 跳过无效数据
            if pd.isna(R) or pd.isna(N):
                continue
            if not isinstance(R, (int, float)) or not isinstance(N, (int, float)):
                continue
            
            all_params[sample_id] = {
                'R': float(R),
                'N': float(N),
                'L_cm': float(L) if isinstance(L, (int, float)) else 0.12,
                'S_cm2': float(S) if isinstance(S, (int, float)) else 3.919348,
                'material': 'Sepiolite',
                'acid': 'H3PO4',
            }
    except Exception as e:
        print(f"读取S8数据失败: {e}")
    
    # 读取S60
    try:
        df_s60 = pd.read_excel(excel_path, sheet_name='S60')
        for idx, row in df_s60.iterrows():
            if idx == 0:
                continue
            sample_id = row.iloc[1]
            if pd.isna(sample_id) or not str(sample_id).startswith('S60-'):
                continue
            
            # S60的R值在不同位置，需要特殊处理
            # S60是纯液体，N=0
            R = row.iloc[14] if not pd.isna(row.iloc[14]) else 0  # 酸水摩尔比
            L = row.iloc[20] if not pd.isna(row.iloc[20]) else 0.7
            S = row.iloc[21] if not pd.isna(row.iloc[21]) else 0.1963
            
            all_params[sample_id] = {
                'R': float(R) if isinstance(R, (int, float)) else 0,
                'N': 0.0,  # S60无黏土
                'L_cm': float(L) if isinstance(L, (int, float)) else 0.7,
                'S_cm2': float(S) if isinstance(S, (int, float)) else 0.1963,
                'material': 'Bulk_H3PO4',
                'acid': 'H3PO4',
            }
    except Exception as e:
        print(f"读取S60数据失败: {e}")
    
    return all_params


# 预加载参数（首次导入时执行）
_MATERIAL_PARAMS = None


def get_material_params(sample_id: str) -> Optional[Dict]:
    """
    获取材料参数
    
    Args:
        sample_id: 样品ID，如 "S8-3-2" 或 "S8-3-2-1"
    
    Returns:
        参数字典 {R, N, L_cm, S_cm2, material, acid}
    """
    global _MATERIAL_PARAMS
    
    if _MATERIAL_PARAMS is None:
        _MATERIAL_PARAMS = load_material_params_from_excel()
    
    # 直接匹配
    if sample_id in _MATERIAL_PARAMS:
        return _MATERIAL_PARAMS[sample_id].copy()
    
    # 尝试匹配前缀 (S8-3-2-1 → S8-3-2)
    parts = sample_id.split('-')
    for i in range(len(parts), 1, -1):
        prefix = '-'.join(parts[:i])
        if prefix in _MATERIAL_PARAMS:
            return _MATERIAL_PARAMS[prefix].copy()
    
    return None


def print_s8_params():
    """打印S8的所有参数"""
    params = load_material_params_from_excel()
    
    s8_params = {k: v for k, v in params.items() if k.startswith('S8-')}
    
    print("=" * 70)
    print("S8材料参数（从Excel正确提取）")
    print("=" * 70)
    print(f"\n总样品数: {len(s8_params)}")
    
    # 统计R-N组合
    rn_groups = {}
    for sample_id, p in sorted(s8_params.items()):
        rn_key = f"R={p['R']:.4f}_N={p['N']:.2f}"
        if rn_key not in rn_groups:
            rn_groups[rn_key] = []
        rn_groups[rn_key].append(sample_id)
    
    print(f"R-N组合数: {len(rn_groups)}")
    
    print(f"\n{'样品ID':<15} {'R':>10} {'N':>8}")
    print("-" * 40)
    for sample_id, p in sorted(s8_params.items()):
        print(f"{sample_id:<15} {p['R']:>10.4f} {p['N']:>8.2f}")
    
    print(f"\n" + "=" * 70)
    print("R-N组合统计")
    print("=" * 70)
    for rn_key, samples in sorted(rn_groups.items()):
        print(f"\n{rn_key}: {len(samples)} 样品")
        for s in samples[:5]:
            print(f"  - {s}")
        if len(samples) > 5:
            print(f"  ... 还有{len(samples)-5}个")


if __name__ == '__main__':
    print_s8_params()
