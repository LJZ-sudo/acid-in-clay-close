"""Shared project paths for runner scripts under code/."""
from __future__ import annotations

from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = CODE_DIR.parent

STAGE0_DIR = PROJECT_ROOT / "stage0_measurement"
STAGE1_DIR = PROJECT_ROOT / "stage1_optimization"
STAGE2_DIR = PROJECT_ROOT / "stage2_statistics"
STAGE3_DIR = PROJECT_ROOT / "stage3_mechanism"

OUTPUT_DIR = PROJECT_ROOT / "output"
STAGE0_RESULTS = OUTPUT_DIR / "stage0_results"
RAW_EIS_S8 = PROJECT_ROOT / "data" / "raw_eis" / "S8"

