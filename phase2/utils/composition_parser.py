# -*- coding: utf-8 -*-
"""
材料配比解析器
从S8-S60.xlsx提取材料组成信息
"""
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Optional

class CompositionParser:
    """解析S8-S60.xlsx中的材料配比数据"""
    
    def __init__(self, excel_path: str = "data/S8-S60.xlsx"):
        self.excel_path = excel_path
        self.s8_data = None
        self.s60_data = None
        self._load_data()
        
    def _load_data(self):
        """加载Excel数据"""
        try:
            self.s8_data = pd.read_excel(self.excel_path, sheet_name='S8acid in clay')
            self.s60_data = pd.read_excel(self.excel_path, sheet_name='S60acid')
        except Exception as e:
            print(f"Error loading Excel: {e}")
            
    def parse_sample_composition(self, sample_id: str) -> Optional[Dict]:
        """
        解析样品的材料组成
        
        Args:
            sample_id: 样品ID，如"S8-3-2-1"或"S60-2-2-1"
            
        Returns:
            材料组成字典
        """
        # 提取系列和编号
        parts = sample_id.split('-')
        if len(parts) < 2:
            return None
            
        series = parts[0]  # S8 或 S60
        
        # 尝试不同的匹配模式
        # S8-2-1-1 → S8-2-1
        # S8-3-2-1 → S8-3-2
        if len(parts) >= 3:
            sample_num = '-'.join(parts[:3])  # S8-3-2
        else:
            sample_num = '-'.join(parts[:2])  # S8-3
        
        if series == 'S8':
            return self._parse_s8_composition(sample_num)
        elif series == 'S60':
            return self._parse_s60_composition(sample_num)
        else:
            return None
            
    def _parse_s8_composition(self, sample_num: str) -> Optional[Dict]:
        """解析S8系列样品组成"""
        if self.s8_data is None:
            return None
            
        # 在第二列查找样品编号
        row = self.s8_data[self.s8_data.iloc[:, 1] == sample_num]
        
        if row.empty:
            return None
            
        row = row.iloc[0]
        
        # 提取关键数据
        composition = {
            'material_type': 'Acid_in_Clay',
            'has_sepiolite': True,
            
            # Sepiolite
            'sepiolite_weight_mg': 450.0,  # 固定值
            'sepiolite_mol_mmol': row.iloc[3] if pd.notna(row.iloc[3]) else 1.352,
            
            # H3PO4
            'H3PO4_drops': row.iloc[5] if pd.notna(row.iloc[5]) else 0,
            'H3PO4_weight_mg': row.iloc[6] if pd.notna(row.iloc[6]) else 0,
            'H3PO4_to_sepiolite_ratio': row.iloc[7] if pd.notna(row.iloc[7]) else 0,
            
            # H2O
            'H2O_drops': row.iloc[9] if pd.notna(row.iloc[9]) else 0,
            'H2O_weight_mg': row.iloc[10] if pd.notna(row.iloc[10]) else 0,
            'H2O_to_sepiolite_ratio': row.iloc[11] if pd.notna(row.iloc[11]) else 0,
            
            # 总液体
            'total_liquid_weight_mg': row.iloc[12] if pd.notna(row.iloc[12]) else 0,
            
            # 比例
            'H3PO4_to_H2O_ratio': row.iloc[13] if pd.notna(row.iloc[13]) else 0,
            'liquid_to_solid_ratio_N': row.iloc[7] + row.iloc[11] if pd.notna(row.iloc[7]) and pd.notna(row.iloc[11]) else 0,
        }
        
        # 计算H3PO4浓度（wt%）
        total_liquid = composition['H3PO4_weight_mg'] + composition['H2O_weight_mg']
        if total_liquid > 0:
            composition['H3PO4_concentration_wt'] = (composition['H3PO4_weight_mg'] / total_liquid) * 100
        else:
            composition['H3PO4_concentration_wt'] = 0
            
        # 计算摩尔比R
        if composition['H2O_weight_mg'] > 0:
            # H3PO4分子量98，H2O分子量18
            H3PO4_mol = composition['H3PO4_weight_mg'] / 98.0
            H2O_mol = composition['H2O_weight_mg'] / 18.0
            composition['molar_ratio_R'] = H3PO4_mol / H2O_mol if H2O_mol > 0 else float('inf')
        else:
            composition['molar_ratio_R'] = float('inf')
            
        return composition
        
    def _parse_s60_composition(self, sample_num: str) -> Optional[Dict]:
        """解析S60系列样品组成"""
        if self.s60_data is None:
            return None
            
        # 在第二列查找样品编号
        row = self.s60_data[self.s60_data.iloc[:, 1] == sample_num]
        
        if row.empty:
            return None
            
        row = row.iloc[0]
        
        # 提取关键数据
        composition = {
            'material_type': 'Pure_Acid',
            'has_sepiolite': False,
            
            # 无Sepiolite
            'sepiolite_weight_mg': 0,
            'sepiolite_mol_mmol': 0,
            
            # H3PO4
            'H3PO4_drops': row.iloc[5] if pd.notna(row.iloc[5]) else 0,
            'H3PO4_weight_mg': row.iloc[6] if pd.notna(row.iloc[6]) else 0,
            
            # H2O
            'H2O_drops': row.iloc[9] if pd.notna(row.iloc[9]) else 0,
            'H2O_weight_mg': row.iloc[10] if pd.notna(row.iloc[10]) else 0,
            
            # H3PO4浓度（直接从Excel读取）
            'H3PO4_concentration_wt': row.iloc[11] if pd.notna(row.iloc[11]) else 0,
            
            # 比例
            'H3PO4_to_H2O_ratio': row.iloc[14] if pd.notna(row.iloc[14]) else 0,
            'liquid_to_solid_ratio_N': 0,  # 无固体
        }
        
        # 计算摩尔比R
        if composition['H2O_weight_mg'] > 0:
            H3PO4_mol = composition['H3PO4_weight_mg'] / 98.0
            H2O_mol = composition['H2O_weight_mg'] / 18.0
            composition['molar_ratio_R'] = H3PO4_mol / H2O_mol if H2O_mol > 0 else float('inf')
        else:
            composition['molar_ratio_R'] = float('inf')
            
        return composition
        
    def get_composition_category(self, composition: Dict) -> str:
        """
        根据组成判断类别
        
        Returns:
            类别字符串
        """
        if composition['has_sepiolite']:
            # S8系列
            conc = composition['H3PO4_concentration_wt']
            if conc > 60:
                return 'S8_high_H3PO4'
            elif conc > 30:
                return 'S8_medium_H3PO4'
            else:
                return 'S8_low_H3PO4'
        else:
            # S60系列
            conc = composition['H3PO4_concentration_wt']
            if conc > 85:
                return 'S60_very_high_H3PO4'
            elif conc > 60:
                return 'S60_high_H3PO4'
            elif conc > 30:
                return 'S60_medium_H3PO4'
            else:
                return 'S60_low_H3PO4'
                
    def get_expected_mechanism(self, composition: Dict) -> str:
        """
        根据组成预测主导机制
        
        Returns:
            预期机制
        """
        category = self.get_composition_category(composition)
        
        mechanism_map = {
            'S8_high_H3PO4': 'Vehicle/Mixed',
            'S8_medium_H3PO4': 'Mixed',
            'S8_low_H3PO4': 'Grotthuss',
            'S60_very_high_H3PO4': 'Vehicle',
            'S60_high_H3PO4': 'Vehicle/Mixed',
            'S60_medium_H3PO4': 'Mixed',
            'S60_low_H3PO4': 'Grotthuss',
        }
        
        return mechanism_map.get(category, 'Unknown')
        
    def get_expected_Ea_range(self, composition: Dict) -> tuple:
        """
        根据组成预测激活能范围
        
        Returns:
            (Ea_min, Ea_max) in eV
        """
        category = self.get_composition_category(composition)
        
        Ea_map = {
            'S8_high_H3PO4': (0.35, 0.45),
            'S8_medium_H3PO4': (0.25, 0.35),
            'S8_low_H3PO4': (0.15, 0.25),
            'S60_very_high_H3PO4': (0.45, 0.60),
            'S60_high_H3PO4': (0.35, 0.50),
            'S60_medium_H3PO4': (0.20, 0.35),
            'S60_low_H3PO4': (0.08, 0.15),  # 高温
        }
        
        return Ea_map.get(category, (0.1, 0.6))

def test_parser():
    """测试解析器"""
    parser = CompositionParser()
    
    # 测试S8样品
    test_samples = [
        'S8-2-1-1',
        'S8-3-2-1',
        'S60-1-1-1',
        'S60-2-2-1',
    ]
    
    for sample_id in test_samples:
        print(f"\n{'='*60}")
        print(f"Sample: {sample_id}")
        print('='*60)
        
        comp = parser.parse_sample_composition(sample_id)
        if comp:
            print(f"Material Type: {comp['material_type']}")
            print(f"Has Sepiolite: {comp['has_sepiolite']}")
            print(f"H3PO4: {comp['H3PO4_weight_mg']:.1f} mg ({comp['H3PO4_drops']:.0f} drops)")
            print(f"H2O: {comp['H2O_weight_mg']:.1f} mg ({comp['H2O_drops']:.0f} drops)")
            print(f"H3PO4 Concentration: {comp['H3PO4_concentration_wt']:.1f} wt%")
            print(f"Molar Ratio R: {comp['molar_ratio_R']:.3f}")
            
            category = parser.get_composition_category(comp)
            mechanism = parser.get_expected_mechanism(comp)
            Ea_range = parser.get_expected_Ea_range(comp)
            
            print(f"\nCategory: {category}")
            print(f"Expected Mechanism: {mechanism}")
            print(f"Expected Ea Range: {Ea_range[0]:.2f} - {Ea_range[1]:.2f} eV")
        else:
            print("Composition not found")

if __name__ == '__main__':
    test_parser()

