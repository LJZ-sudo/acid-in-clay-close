# -*- coding: utf-8 -*-
"""
全局配置文件

存放系统级默认常量，供整个项目读取

版本：2.0.0 (重构版)
"""

import os
from pathlib import Path

# ============================================================
# 硬件配置
# ============================================================

# 串口配置
DEFAULT_SERIAL_PORT = os.getenv("STAGE0_SERIAL_PORT", "COM3")
DEFAULT_BAUDRATE = 19200
DEFAULT_TIMEOUT = 0.1

# 温度控制配置
DEFAULT_TEMP_MIN = -120.0  # °C
DEFAULT_TEMP_MAX = 25.0    # °C
DEFAULT_TEMP_EPS = 0.5     # 温度容差 (°C)

# 温度稳定性配置
DEFAULT_STABILITY_DURATION = 40      # 秒
DEFAULT_STABILITY_CHECK_INTERVAL = 5  # 秒
DEFAULT_STABILITY_MAX_RETRY = 3       # 次

# ============================================================
# 实验配置
# ============================================================

# 降温配置
DEFAULT_COOLING_T_START = 25.0    # 起始温度 (°C)
DEFAULT_COOLING_T_END = -120.0    # 结束温度 (°C)
DEFAULT_COARSE_STEP = 3.0         # 粗扫步长 (°C)
DEFAULT_FINE_STEP = 1.0           # 细扫步长 (°C)

# 测量配置
DEFAULT_MEASUREMENT_MAX_RETRY = 3  # 测量最大重试次数

# ============================================================
# CHI 配置
# ============================================================

# CHI 参数
DEFAULT_CHI_HIGHF = "1000000"  # 高频 (Hz)
DEFAULT_CHI_LOWF = "0.1"       # 低频 (Hz)
DEFAULT_CHI_INITV = "0"        # 初始电位 (V)

# 样品参数
DEFAULT_THICKNESS_CM = 0.1     # 样品厚度 (cm)
DEFAULT_AREA_CM2 = 1.96        # 样品面积 (cm²)

# 在线实验：电导率硬熔断默认阈值 (S/cm)
DEFAULT_MIN_CONDUCTIVITY_THRESHOLD = 1e-8

# 在线实验状态快照（断点续测）默认文件名（相对 stage0_measurement 目录）
ONLINE_EXPERIMENT_STATE_FILENAME = "online_experiment_state.json"

# 数据目录
_STAGE0_ROOT = Path(__file__).parent
DEFAULT_CHI_DATA_DIR = os.getenv(
    "STAGE0_CHI_DATA_DIR",
    str(_STAGE0_ROOT / "data" / "chi_measurements")
)
# 与仓库内实际目录一致：stage0_measurement/controllers/templates/
DEFAULT_CHI_TEMPLATE_DIR = os.getenv(
    "STAGE0_CHI_TEMPLATE_DIR",
    str(_STAGE0_ROOT / "controllers" / "templates")
)

# ============================================================
# 分析配置
# ============================================================

# 数据质量阈值
MIN_DATA_POINTS = 10           # 最小数据点数
MIN_FREQUENCY = 0.01           # 最小频率 (Hz)
MAX_FREQUENCY = 1e6            # 最大频率 (Hz)

# 拟合质量阈值
MIN_R_SQUARED = 0.8            # 最小 R² 值
MIN_FIT_QUALITY = 0.7          # 最小拟合质量

# 自动停止阈值
MAX_RB_OHM = 1e6               # 最大 Rb 值 (Ω)
MIN_CONDUCTIVITY_S_CM = 1e-8   # 最小电导率 (S/cm)
MAX_CONSECUTIVE_FAILURES = 3   # 最大连续失败次数

# ============================================================
# 离线批处理配置
# ============================================================

# 文件匹配模式
DEFAULT_CHI_FILE_PATTERN = "*.txt"
DEFAULT_DTA_FILE_PATTERN = "*.dta"

# 错误处理
DEFAULT_SKIP_FAILED_FILES = True    # 跳过失败的文件
DEFAULT_CONTINUE_ON_ERROR = True    # 遇到错误是否继续

# 功能开关
DEFAULT_ENABLE_ARRHENIUS = True     # 启用 Arrhenius 分析
DEFAULT_ENABLE_REPORTING = True     # 启用报告生成
DEFAULT_ENABLE_PHASE_DETECTION = True  # 启用相变检测
DEFAULT_ENABLE_AUTO_STOP = True     # 启用自动停止

# ============================================================
# 报告配置
# ============================================================

# AI 报告配置
DEFAULT_AI_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_AI_PRIMARY_MODEL = "gpt-4"
DEFAULT_AI_FALLBACK_MODEL = "gpt-3.5-turbo"
DEFAULT_AI_TEMPERATURE = 0.15
DEFAULT_AI_MAX_TOKENS = 8000
DEFAULT_AI_TIMEOUT = 300  # 秒

# 图表配置
DEFAULT_PLOT_DPI = 300
DEFAULT_PLOT_FIGSIZE = (10, 6)

# ============================================================
# 日志配置
# ============================================================

# 日志级别
DEFAULT_LOG_LEVEL = "INFO"  # DEBUG | INFO | WARNING | ERROR

# 日志格式
DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================
# 系统配置
# ============================================================

# 超时配置
DEFAULT_COOLING_TIMEOUT = 3600       # 降温超时 (秒)
DEFAULT_MEASUREMENT_TIMEOUT = 600    # 测量超时 (秒)
DEFAULT_BATCH_TIMEOUT = 7200         # 批处理超时 (秒)

# 资源限制
MAX_MEMORY_MB = 4096                 # 最大内存使用 (MB)
MAX_CPU_CORES = 4                    # 最大 CPU 核心数

# ============================================================
# 辅助函数
# ============================================================

def get_default_cooling_config():
    """获取默认降温配置"""
    from controllers import CoolingConfig
    
    return CoolingConfig(
        T_start=DEFAULT_COOLING_T_START,
        T_end=DEFAULT_COOLING_T_END,
        coarse_step=DEFAULT_COARSE_STEP,
        fine_step=DEFAULT_FINE_STEP,
        eps=DEFAULT_TEMP_EPS,
        stability_duration=DEFAULT_STABILITY_DURATION,
        stability_check_interval=DEFAULT_STABILITY_CHECK_INTERVAL,
        stability_max_retry=DEFAULT_STABILITY_MAX_RETRY,
        measurement_max_retry=DEFAULT_MEASUREMENT_MAX_RETRY,
    )


def get_default_chi_config(material_name="Sample"):
    """获取默认 CHI 配置"""
    from controllers import ChiConfig
    
    return ChiConfig(
        material=material_name,
        highf=DEFAULT_CHI_HIGHF,
        lowf=DEFAULT_CHI_LOWF,
        initV=DEFAULT_CHI_INITV,
        your_position=DEFAULT_CHI_DATA_DIR,
        template_dir=DEFAULT_CHI_TEMPLATE_DIR,
        thickness_cm=DEFAULT_THICKNESS_CM,
        area_cm2=DEFAULT_AREA_CM2,
    )


def get_default_experiment_config(material_name="Sample"):
    """获取默认实验配置"""
    from controllers import ExperimentConfig
    
    return ExperimentConfig(
        cooling=get_default_cooling_config(),
        chi=get_default_chi_config(material_name),
        enable_phase_detection=DEFAULT_ENABLE_PHASE_DETECTION,
        enable_auto_stop=DEFAULT_ENABLE_AUTO_STOP,
        enable_fine_scan=True,
    )


def get_default_offline_config(data_dir, material_name="Sample"):
    """获取默认离线配置"""
    from controllers import OfflineConfig
    
    return OfflineConfig(
        data_dir=data_dir,
        output_dir="./offline_results",
        chi_file_pattern=DEFAULT_CHI_FILE_PATTERN,
        dta_file_pattern=DEFAULT_DTA_FILE_PATTERN,
        skip_failed_files=DEFAULT_SKIP_FAILED_FILES,
        continue_on_error=DEFAULT_CONTINUE_ON_ERROR,
        enable_arrhenius=DEFAULT_ENABLE_ARRHENIUS,
        enable_reporting=DEFAULT_ENABLE_REPORTING,
        material_name=material_name,
        thickness_cm=DEFAULT_THICKNESS_CM,
        area_cm2=DEFAULT_AREA_CM2,
    )
