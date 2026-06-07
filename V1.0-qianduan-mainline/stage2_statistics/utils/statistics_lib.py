"""
Statistics Library - 底层数学支持
提供 Bootstrap CI, AIC/BIC 计算, 异常值检测等功能
"""

import numpy as np
import pandas as pd
from typing import Callable, Tuple, Optional, Union, List
from scipy import stats


def bootstrap_ci(
    data: Union[np.ndarray, list],
    func: Callable = np.mean,
    n_bootstrap: int = 2000,
    confidence_level: float = 0.95,
    random_seed: Optional[int] = None
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    使用 Bootstrap 重采样方法计算统计量的置信区间
    
    Args:
        data: 输入数据（numpy 数组或列表）
        func: 统计量函数（默认为均值），接受数组返回标量
        n_bootstrap: Bootstrap 重采样次数（默认 2000）
        confidence_level: 置信水平（默认 0.95，即 95% CI）
        random_seed: 随机种子（可选，用于可重复性）
        
    Returns:
        Tuple[stat, ci_lower, ci_upper]: 统计量的点估计和置信区间
            - stat: 原始数据的统计量
            - ci_lower: 置信区间下界
            - ci_upper: 置信区间上界
            - 如果数据不足，返回 (None, None, None)
            
    Examples:
        >>> data = np.array([1.2, 1.5, 1.3, 1.4, 1.6])
        >>> mean, ci_low, ci_high = bootstrap_ci(data, np.mean)
        >>> print(f"Mean: {mean:.2f}, 95% CI: [{ci_low:.2f}, {ci_high:.2f}]")
    """
    # 输入验证和预处理
    if data is None:
        return None, None, None
    
    # 转换为 numpy 数组
    if isinstance(data, list):
        data = np.array(data)
    elif not isinstance(data, np.ndarray):
        try:
            data = np.array(data)
        except Exception:
            return None, None, None
    
    # 移除 NaN 值
    data = data[~np.isnan(data)]
    
    # 检查数据量
    if len(data) < 2:
        if len(data) == 1:
            try:
                stat = float(func(data))
                return stat, None, None
            except Exception:
                return None, None, None
        return None, None, None
    
    # 计算原始统计量
    try:
        original_stat = float(func(data))
    except Exception as e:
        raise ValueError(f"统计量函数执行失败: {e}")
    
    # Bootstrap 重采样
    rng = np.random.default_rng(random_seed)
    bootstrap_stats = []
    
    for _ in range(n_bootstrap):
        # 有放回抽样
        sample = rng.choice(data, size=len(data), replace=True)
        try:
            stat = float(func(sample))
            bootstrap_stats.append(stat)
        except Exception:
            # 如果某次采样失败，跳过
            continue
    
    # 检查 bootstrap 结果
    if len(bootstrap_stats) < n_bootstrap * 0.5:
        # 如果超过一半的 bootstrap 失败，返回 None
        return original_stat, None, None
    
    bootstrap_stats = np.array(bootstrap_stats)
    
    # 计算置信区间（百分位数法）
    alpha = 1 - confidence_level
    try:
        ci_lower = float(np.percentile(bootstrap_stats, alpha / 2 * 100))
        ci_upper = float(np.percentile(bootstrap_stats, (1 - alpha / 2) * 100))
    except Exception:
        return original_stat, None, None
    
    return original_stat, ci_lower, ci_upper


def calculate_aic(
    n: int,
    rss: float,
    k: int
) -> Optional[float]:
    """
    计算 Akaike Information Criterion (AIC)
    
    AIC = n * ln(RSS/n) + 2k
    
    Args:
        n: 样本数量
        rss: 残差平方和 (Residual Sum of Squares)
        k: 模型参数数量（包括截距）
        
    Returns:
        float: AIC 值，越小越好
        None: 如果输入无效
        
    Notes:
        - AIC 用于模型比选，惩罚参数过多的模型
        - 对于小样本（n/k < 40），建议使用 AICc（修正 AIC）
        
    Examples:
        >>> aic = calculate_aic(n=100, rss=50.5, k=3)
        >>> print(f"AIC: {aic:.2f}")
    """
    # 输入验证
    if n <= 0:
        return None
    
    if rss < 0:
        return None
    
    if k < 0:
        return None
    
    if k >= n:
        # 参数数量不能大于等于样本数量
        return None
    
    # 处理 RSS = 0 的情况
    if rss == 0:
        # RSS 为 0 表示完美拟合，返回一个很小的 AIC
        # 但实际上这种情况通常不合理（过拟合）
        return 2 * k
    
    # 计算 AIC
    try:
        aic = n * np.log(rss / n) + 2 * k
        return float(aic)
    except Exception:
        return None


def calculate_bic(
    n: int,
    rss: float,
    k: int
) -> Optional[float]:
    """
    计算 Bayesian Information Criterion (BIC)
    
    BIC = n * ln(RSS/n) + k * ln(n)
    
    Args:
        n: 样本数量
        rss: 残差平方和 (Residual Sum of Squares)
        k: 模型参数数量（包括截距）
        
    Returns:
        float: BIC 值，越小越好
        None: 如果输入无效
        
    Notes:
        - BIC 比 AIC 对参数数量的惩罚更严格（当 n > 7 时）
        - BIC 更倾向于选择简单模型
        
    Examples:
        >>> bic = calculate_bic(n=100, rss=50.5, k=3)
        >>> print(f"BIC: {bic:.2f}")
    """
    # 输入验证
    if n <= 0:
        return None
    
    if rss < 0:
        return None
    
    if k < 0:
        return None
    
    if k >= n:
        return None
    
    # 处理 RSS = 0 的情况
    if rss == 0:
        return k * np.log(n)
    
    # 计算 BIC
    try:
        bic = n * np.log(rss / n) + k * np.log(n)
        return float(bic)
    except Exception:
        return None


def calculate_aicc(
    n: int,
    rss: float,
    k: int
) -> Optional[float]:
    """
    计算修正 AIC (AICc) - 适用于小样本
    
    AICc = AIC + 2k(k+1)/(n-k-1)
    
    Args:
        n: 样本数量
        rss: 残差平方和
        k: 模型参数数量
        
    Returns:
        float: AICc 值
        None: 如果输入无效
        
    Notes:
        - 当 n/k < 40 时，推荐使用 AICc 而非 AIC
        - 当 n 很大时，AICc 收敛到 AIC
    """
    # 计算 AIC
    aic = calculate_aic(n, rss, k)
    if aic is None:
        return None
    
    # 检查分母
    if n - k - 1 <= 0:
        return None
    
    # 计算修正项
    try:
        correction = 2 * k * (k + 1) / (n - k - 1)
        aicc = aic + correction
        return float(aicc)
    except Exception:
        return None


def detect_outliers_iqr(
    df: pd.DataFrame,
    column: str,
    multiplier: float = 1.5
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    使用四分位距 (IQR) 方法检测异常值
    
    异常值定义：
        - 下界异常值: x < Q1 - multiplier * IQR
        - 上界异常值: x > Q3 + multiplier * IQR
    
    Args:
        df: 输入 DataFrame
        column: 要检测异常值的列名
        multiplier: IQR 倍数（默认 1.5，经典 Tukey 方法）
            - 1.5: 温和异常值检测
            - 3.0: 极端异常值检测
            
    Returns:
        Tuple[clean_df, outliers_df, stats]:
            - clean_df: 移除异常值后的 DataFrame
            - outliers_df: 异常值的 DataFrame
            - stats: 统计信息字典
            
    Examples:
        >>> df = pd.DataFrame({'value': [1, 2, 3, 4, 5, 100]})
        >>> clean, outliers, stats = detect_outliers_iqr(df, 'value')
        >>> print(f"检测到 {stats['n_outliers']} 个异常值")
    """
    # 输入验证
    if df is None or df.empty:
        return df, pd.DataFrame(), {
            'n_total': 0,
            'n_outliers': 0,
            'n_clean': 0,
            'outlier_ratio': 0.0
        }
    
    if column not in df.columns:
        raise ValueError(f"列 '{column}' 不存在于 DataFrame 中")
    
    # 提取列数据（移除 NaN）
    data = df[column].dropna()
    
    if len(data) < 4:
        # 数据点太少，无法计算 IQR
        return df, pd.DataFrame(), {
            'n_total': len(df),
            'n_outliers': 0,
            'n_clean': len(df),
            'outlier_ratio': 0.0,
            'warning': '数据点不足 4 个，无法进行 IQR 异常值检测'
        }
    
    # 计算四分位数
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    IQR = Q3 - Q1
    
    # 计算异常值边界
    lower_bound = Q1 - multiplier * IQR
    upper_bound = Q3 + multiplier * IQR
    
    # 标记异常值
    outlier_mask = (df[column] < lower_bound) | (df[column] > upper_bound)
    
    # 分离正常值和异常值
    clean_df = df[~outlier_mask].copy()
    outliers_df = df[outlier_mask].copy()
    
    # 统计信息
    n_total = len(df)
    n_outliers = len(outliers_df)
    n_clean = len(clean_df)
    
    stats = {
        'n_total': n_total,
        'n_outliers': n_outliers,
        'n_clean': n_clean,
        'outlier_ratio': n_outliers / n_total if n_total > 0 else 0.0,
        'Q1': float(Q1),
        'Q3': float(Q3),
        'IQR': float(IQR),
        'lower_bound': float(lower_bound),
        'upper_bound': float(upper_bound),
        'multiplier': multiplier,
        'column': column
    }
    
    return clean_df, outliers_df, stats


def detect_outliers_zscore(
    df: pd.DataFrame,
    column: str,
    threshold: float = 3.0
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    使用 Z-score 方法检测异常值
    
    异常值定义：|Z-score| > threshold
    
    Args:
        df: 输入 DataFrame
        column: 要检测异常值的列名
        threshold: Z-score 阈值（默认 3.0）
            - 3.0: 99.7% 置信区间（经典阈值）
            - 2.5: 98.8% 置信区间
            
    Returns:
        Tuple[clean_df, outliers_df, stats]
        
    Notes:
        - 假设数据服从正态分布
        - 对于非正态分布，建议使用 IQR 方法
    """
    # 输入验证
    if df is None or df.empty:
        return df, pd.DataFrame(), {
            'n_total': 0,
            'n_outliers': 0,
            'n_clean': 0,
            'outlier_ratio': 0.0
        }
    
    if column not in df.columns:
        raise ValueError(f"列 '{column}' 不存在于 DataFrame 中")
    
    # 提取列数据（移除 NaN）
    data = df[column].dropna()
    
    if len(data) < 3:
        return df, pd.DataFrame(), {
            'n_total': len(df),
            'n_outliers': 0,
            'n_clean': len(df),
            'outlier_ratio': 0.0,
            'warning': '数据点不足 3 个，无法进行 Z-score 异常值检测'
        }
    
    # 计算 Z-score
    mean = data.mean()
    std = data.std()
    
    if std == 0:
        # 标准差为 0，所有值相同，无异常值
        return df, pd.DataFrame(), {
            'n_total': len(df),
            'n_outliers': 0,
            'n_clean': len(df),
            'outlier_ratio': 0.0,
            'mean': float(mean),
            'std': 0.0,
            'warning': '标准差为 0，所有值相同'
        }
    
    z_scores = np.abs((df[column] - mean) / std)
    
    # 标记异常值
    outlier_mask = z_scores > threshold
    
    # 分离正常值和异常值
    clean_df = df[~outlier_mask].copy()
    outliers_df = df[outlier_mask].copy()
    
    # 统计信息
    n_total = len(df)
    n_outliers = len(outliers_df)
    n_clean = len(clean_df)
    
    stats = {
        'n_total': n_total,
        'n_outliers': n_outliers,
        'n_clean': n_clean,
        'outlier_ratio': n_outliers / n_total if n_total > 0 else 0.0,
        'mean': float(mean),
        'std': float(std),
        'threshold': threshold,
        'column': column
    }
    
    return clean_df, outliers_df, stats


def compare_models(
    model_results: List[dict],
    criterion: str = 'aic'
) -> dict:
    """
    比较多个模型，选择最优模型
    
    Args:
        model_results: 模型结果列表，每个元素为字典，包含：
            - 'name': 模型名称
            - 'n': 样本数量
            - 'rss': 残差平方和
            - 'k': 参数数量
            - 其他可选信息
        criterion: 比较准则 ('aic', 'bic', 'aicc')
        
    Returns:
        dict: 包含最优模型信息和所有模型的比较结果
        
    Examples:
        >>> models = [
        ...     {'name': 'Arrhenius', 'n': 50, 'rss': 10.5, 'k': 2},
        ...     {'name': 'VTF', 'n': 50, 'rss': 8.2, 'k': 3}
        ... ]
        >>> result = compare_models(models, criterion='aic')
        >>> print(f"最优模型: {result['best_model']['name']}")
    """
    if not model_results:
        return {
            'best_model': None,
            'comparison': [],
            'error': '没有提供模型结果'
        }
    
    # 计算每个模型的信息准则
    comparison = []
    for model in model_results:
        if not all(k in model for k in ['name', 'n', 'rss', 'k']):
            continue
        
        n, rss, k = model['n'], model['rss'], model['k']
        
        # 计算信息准则
        if criterion.lower() == 'aic':
            ic = calculate_aic(n, rss, k)
        elif criterion.lower() == 'bic':
            ic = calculate_bic(n, rss, k)
        elif criterion.lower() == 'aicc':
            ic = calculate_aicc(n, rss, k)
        else:
            raise ValueError(f"未知的准则: {criterion}")
        
        if ic is not None:
            comparison.append({
                'name': model['name'],
                'n': n,
                'rss': rss,
                'k': k,
                criterion: ic,
                **{k: v for k, v in model.items() if k not in ['name', 'n', 'rss', 'k']}
            })
    
    if not comparison:
        return {
            'best_model': None,
            'comparison': [],
            'error': '所有模型的信息准则计算失败'
        }
    
    # 按信息准则排序（越小越好）
    comparison.sort(key=lambda x: x[criterion])
    
    # 计算相对差异（Delta IC）
    best_ic = comparison[0][criterion]
    for model in comparison:
        model[f'delta_{criterion}'] = model[criterion] - best_ic
    
    return {
        'best_model': comparison[0],
        'comparison': comparison,
        'criterion': criterion,
        'n_models': len(comparison)
    }


def calculate_r_squared(
    y_true: np.ndarray,
    y_pred: np.ndarray
) -> Optional[float]:
    """
    计算决定系数 R²
    
    R² = 1 - (SS_res / SS_tot)
    
    Args:
        y_true: 真实值
        y_pred: 预测值
        
    Returns:
        float: R² 值 [0, 1]，越接近 1 越好
        None: 如果输入无效
    """
    if y_true is None or y_pred is None:
        return None
    
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    # 移除 NaN
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true = y_true[mask]
    y_pred = y_pred[mask]
    
    if len(y_true) < 2:
        return None
    
    if len(y_true) != len(y_pred):
        return None
    
    # 计算残差平方和
    ss_res = np.sum((y_true - y_pred) ** 2)
    
    # 计算总平方和
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    
    if ss_tot == 0:
        # 所有真实值相同
        return 1.0 if ss_res == 0 else 0.0
    
    r_squared = 1 - (ss_res / ss_tot)
    
    return float(r_squared)


def calculate_adjusted_r_squared(
    r_squared: float,
    n: int,
    k: int
) -> Optional[float]:
    """
    计算调整 R² (Adjusted R²)
    
    Adjusted R² = 1 - (1 - R²) * (n - 1) / (n - k - 1)
    
    Args:
        r_squared: R² 值
        n: 样本数量
        k: 自变量数量（不包括截距）
        
    Returns:
        float: 调整 R² 值
        None: 如果输入无效
        
    Notes:
        - 调整 R² 惩罚参数过多的模型
        - 可能为负值（表示模型很差）
    """
    if r_squared is None or n <= 0 or k < 0:
        return None
    
    if n - k - 1 <= 0:
        return None
    
    adj_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - k - 1)
    
    return float(adj_r_squared)
