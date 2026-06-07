"""路径常量与路径辅助函数。"""
from __future__ import annotations
from pathlib import Path

# 项目根（stage3_mechanism/）
ROOT = Path(__file__).parent.parent.parent.parent

SRC_DIR   = ROOT / "src"
DATA_DIR  = ROOT / "data"
INPUT_DIR = ROOT / "data" / "input"
CACHE_DIR = ROOT / "data" / "cache"
OUTPUT_DIR = ROOT / "outputs" / "stage3"
PROMPTS_DIR = SRC_DIR / "s8_stage3" / "prompts"
LOGS_DIR  = ROOT / "logs"

# 真实输入优先路径（从 stage3_mechanism/input/ 读）
REAL_INPUT_DIR = ROOT / "input"


def ensure_output_dirs() -> None:
    """确保所有标准输出目录存在。"""
    for subdir in [
        "00_preprocess", "00_seed_real", "01_evidence", "02_hypotheses",
        "03_literature_mechanism", "04_mechanism", "05_descriptors",
        "06_literature_materials", "07_material_families",
        "08_material_instances", "09_ranking", "10_reports",
    ]:
        (OUTPUT_DIR / subdir).mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
