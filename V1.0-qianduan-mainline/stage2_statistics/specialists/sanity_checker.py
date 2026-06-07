"""
Sanity Checker - 数据清洗专家
过滤低质量数据和不合理的数值
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

try:
    from ..core.base_specialist import BaseSpecialist
    from ..core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
    from ..config import Config
except ImportError:
    from core.base_specialist import BaseSpecialist
    from core.schema import EvidenceUnit, ClaimLevel, EvidenceTheme
    from config import Config


class SanityChecker(BaseSpecialist):
    """
    数据清洗专家
    
    核心任务：
    1. 基于 R² 过滤低质量拟合数据
    2. 移除不合理的 Ea 值（物理上不可能的范围）
    3. 移除异常的 sigma 值
    4. 检测并报告数据质量问题
    """
    
    def __init__(
        self,
        name: str = "SanityChecker",
        r2_threshold: float = None,
        ea_range: Tuple[float, float] = None,
        sigma_range: Tuple[float, float] = None,
        enable_outlier_detection: bool = False
    ):
        """
        初始化数据清洗器
        
        Args:
            name: 专家名称
            r2_threshold: R² 阈值（低于此值的数据将被过滤）
            ea_range: Ea 合理范围 (eV)，典型值 0.1-2.0 eV
            sigma_range: sigma 合理范围 (S/cm)
            enable_outlier_detection: 是否启用统计异常值检测
        """
        super().__init__(name)
        # 使用配置文件中的默认值
        self.r2_threshold = r2_threshold if r2_threshold is not None else Config.sanity_check.R2_THRESHOLD
        self.ea_range = ea_range if ea_range is not None else Config.sanity_check.EA_RANGE
        self.sigma_range = sigma_range if sigma_range is not None else Config.sanity_check.SIGMA_RANGE
        self.enable_outlier_detection = enable_outlier_detection
    
    def analyze(
        self,
        data: pd.DataFrame,
        profile: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceUnit]:
        """
        分析数据质量并生成证据
        
        注意：这个方法生成证据，实际的数据清洗在 filter_data() 中
        
        Args:
            data: 输入数据（清洗前）
            profile: 数据画像
            
        Returns:
            List[EvidenceUnit]: 数据质量相关的证据
        """
        evidences = []
        
        if data is None or data.empty:
            return evidences
        
        # 统计清洗前的数据
        original_count = len(data)
        
        # 统计各种问题
        stats_dict = self._calculate_filter_statistics(data)
        
        total_filtered = (
            stats_dict['low_r2_count'] +
            stats_dict['invalid_ea_count'] +
            stats_dict['invalid_sigma_count'] +
            stats_dict['nan_count']
        )
        
        # 生成数据质量证据
        if total_filtered > 0:
            filter_ratio = total_filtered / original_count
            
            # 构建详细说明
            details = []
            if stats_dict['low_r2_count'] > 0:
                details.append(f"R² < {self.r2_threshold} 的有 {stats_dict['low_r2_count']} 个")
            if stats_dict['invalid_ea_count'] > 0:
                details.append(f"Ea 超出合理范围 [{self.ea_range[0]}, {self.ea_range[1]}] eV 的有 {stats_dict['invalid_ea_count']} 个")
            if stats_dict['invalid_sigma_count'] > 0:
                details.append(f"sigma 异常的有 {stats_dict['invalid_sigma_count']} 个")
            if stats_dict['nan_count'] > 0:
                details.append(f"包含 NaN 的有 {stats_dict['nan_count']} 个")
            
            statement = (
                f"数据清洗：从 {original_count} 个样本中识别出 {total_filtered} 个低质量数据点 "
                f"({filter_ratio*100:.1f}%)。" + "，".join(details) + "。"
            )
            
            # 根据过滤比例确定置信度
            confidence = 1.0 if filter_ratio < 0.3 else 0.8
            
            evidence = EvidenceUnit(
                claim_level=ClaimLevel.observation,
                theme=EvidenceTheme.transport_dynamics,
                statement=statement,
                support_metrics={
                    'original_count': int(original_count),
                    'filtered_count': int(total_filtered),
                    'filter_ratio': float(filter_ratio),
                    'low_r2_count': int(stats_dict['low_r2_count']),
                    'invalid_ea_count': int(stats_dict['invalid_ea_count']),
                    'invalid_sigma_count': int(stats_dict['invalid_sigma_count']),
                    'nan_count': int(stats_dict['nan_count']),
                    'r2_threshold': self.r2_threshold,
                    'ea_range': list(self.ea_range),
                    'sigma_range': [float(self.sigma_range[0]), float(self.sigma_range[1])]
                },
                confidence=confidence,
                confidence_basis={
                    'rule_id': 'sanity_filter_ratio',
                    'formula': '1.0 if filter_ratio < 0.3 else 0.8',
                    'inputs': {'filter_ratio': float(filter_ratio)},
                    'interpretation': '数据清洗证据权重；不是严格统计置信概率'
                },
                tags=['data_quality', 'sanity_check']
            )
            evidences.append(evidence)
        else:
            # 所有数据都通过清洗
            evidence = EvidenceUnit(
                claim_level=ClaimLevel.observation,
                theme=EvidenceTheme.transport_dynamics,
                statement=f"数据质量检查：所有 {original_count} 个样本均通过质量检查，无需过滤。",
                support_metrics={
                    'original_count': int(original_count),
                    'filtered_count': 0,
                    'filter_ratio': 0.0,
                    'r2_threshold': self.r2_threshold
                },
                confidence=1.0,
                confidence_basis={
                    'rule_id': 'sanity_all_pass',
                    'formula': '1.0 when no row violates configured sanity rules',
                    'inputs': {'filter_ratio': 0.0},
                    'interpretation': '所有行通过配置的清洗规则'
                },
                tags=['data_quality', 'high_quality']
            )
            evidences.append(evidence)
        
        return evidences
    
    def filter_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        实际执行数据过滤
        
        Args:
            data: 输入数据
            
        Returns:
            pd.DataFrame: 清洗后的数据
        """
        if data is None or data.empty:
            return data
        
        valid_mask = self._build_valid_mask(data)
        filtered = data[valid_mask].copy()
        
        # 统计异常值检测（如果启用）
        if self.enable_outlier_detection and 'Ea' in filtered.columns:
            filtered = self._remove_outliers_iqr(filtered, 'Ea')

        return filtered

    def build_exclusion_report(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        生成逐行排除原因表，用于 supplementary / 审计输出。

        Args:
            data: 输入数据

        Returns:
            pd.DataFrame: 被排除行及原因
        """
        if data is None or data.empty:
            return pd.DataFrame(columns=[
                'row_index', 'sample_id', 'rule_id', 'column',
                'value', 'threshold', 'reason'
            ])

        records = []

        def add_record(idx, row, rule_id, column, value, threshold, reason):
            records.append({
                'row_index': int(idx) if isinstance(idx, (int, np.integer)) else str(idx),
                'sample_id': row.get('sample_id', ''),
                'rule_id': rule_id,
                'column': column,
                'value': self._safe_scalar(value),
                'threshold': threshold,
                'reason': reason
            })

        for idx, row in data.iterrows():
            if 'R2' in data.columns and pd.notna(row.get('R2')) and row.get('R2') < self.r2_threshold:
                add_record(
                    idx, row, 'low_r2', 'R2', row.get('R2'),
                    f'>= {self.r2_threshold}', 'R2 低于拟合质量阈值'
                )

            if 'Ea' in data.columns and pd.notna(row.get('Ea')):
                ea = row.get('Ea')
                if ea < self.ea_range[0] or ea > self.ea_range[1]:
                    add_record(
                        idx, row, 'invalid_ea', 'Ea', ea,
                        f'[{self.ea_range[0]}, {self.ea_range[1]}]',
                        'Ea 超出配置的物理合理范围'
                    )

            if 'sigma' in data.columns and pd.notna(row.get('sigma')):
                sigma = row.get('sigma')
                if sigma < self.sigma_range[0] or sigma > self.sigma_range[1]:
                    add_record(
                        idx, row, 'invalid_sigma', 'sigma', sigma,
                        f'[{self.sigma_range[0]}, {self.sigma_range[1]}]',
                        'sigma 超出配置的合理范围'
                    )

            key_columns = [col for col in ['Ea', 'R', 'N', 'T'] if col in data.columns]
            for col in key_columns:
                if pd.isna(row.get(col)):
                    add_record(
                        idx, row, 'missing_required_value', col, row.get(col),
                        'not null', f'关键列 {col} 缺失'
                    )

        return pd.DataFrame.from_records(records)

    def _build_valid_mask(self, data: pd.DataFrame) -> pd.Series:
        """根据所有清洗规则构建保留行 mask。"""
        valid_mask = pd.Series(True, index=data.index)

        if 'R2' in data.columns:
            valid_mask &= data['R2'] >= self.r2_threshold

        if 'Ea' in data.columns:
            valid_mask &= (data['Ea'] >= self.ea_range[0]) & (data['Ea'] <= self.ea_range[1])

        if 'sigma' in data.columns:
            valid_mask &= (data['sigma'] >= self.sigma_range[0]) & (data['sigma'] <= self.sigma_range[1])

        key_columns = [col for col in ['Ea', 'R', 'N', 'T'] if col in data.columns]
        if key_columns:
            valid_mask &= ~data[key_columns].isna().any(axis=1)

        return valid_mask

    def _safe_scalar(self, value):
        """将 numpy/pandas 标量转成 JSON/CSV 友好的值。"""
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer, np.int64, np.int32)):
            return int(value)
        if isinstance(value, (np.floating, np.float64, np.float32)):
            return float(value)
        return value
    
    def _calculate_filter_statistics(self, data: pd.DataFrame) -> Dict[str, int]:
        """
        计算各类过滤统计
        
        Args:
            data: 输入数据
            
        Returns:
            Dict[str, int]: 统计字典
        """
        stats_dict = {
            'low_r2_count': 0,
            'invalid_ea_count': 0,
            'invalid_sigma_count': 0,
            'nan_count': 0
        }
        
        # 统计低 R² 数据
        if 'R2' in data.columns:
            stats_dict['low_r2_count'] = int((data['R2'] < self.r2_threshold).sum())
        
        # 统计不合理的 Ea
        if 'Ea' in data.columns:
            stats_dict['invalid_ea_count'] = int((
                (data['Ea'] < self.ea_range[0]) | 
                (data['Ea'] > self.ea_range[1])
            ).sum())
        
        # 统计异常的 sigma
        if 'sigma' in data.columns:
            stats_dict['invalid_sigma_count'] = int((
                (data['sigma'] < self.sigma_range[0]) | 
                (data['sigma'] > self.sigma_range[1])
            ).sum())
        
        # 统计 NaN
        key_columns = [col for col in ['Ea', 'R', 'N', 'T'] if col in data.columns]
        if key_columns:
            stats_dict['nan_count'] = int(data[key_columns].isna().any(axis=1).sum())
        
        return stats_dict
    
    def _remove_outliers_iqr(
        self,
        data: pd.DataFrame,
        column: str,
        multiplier: float = 1.5
    ) -> pd.DataFrame:
        """
        使用 IQR 方法移除异常值
        
        Args:
            data: 输入数据
            column: 要检测的列
            multiplier: IQR 倍数
            
        Returns:
            pd.DataFrame: 移除异常值后的数据
        """
        if column not in data.columns or len(data) < 4:
            return data
        
        Q1 = data[column].quantile(0.25)
        Q3 = data[column].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        
        filtered = data[
            (data[column] >= lower_bound) &
            (data[column] <= upper_bound)
        ]
        
        return filtered
    
    def get_filter_summary(self, data_before: pd.DataFrame, data_after: pd.DataFrame) -> Dict[str, Any]:
        """
        获取过滤摘要
        
        Args:
            data_before: 过滤前的数据
            data_after: 过滤后的数据
            
        Returns:
            Dict[str, Any]: 过滤摘要
        """
        return {
            'original_count': len(data_before),
            'filtered_count': len(data_after),
            'removed_count': len(data_before) - len(data_after),
            'removal_ratio': (len(data_before) - len(data_after)) / len(data_before) if len(data_before) > 0 else 0,
            'r2_threshold': self.r2_threshold,
            'ea_range': self.ea_range,
            'sigma_range': self.sigma_range
        }
