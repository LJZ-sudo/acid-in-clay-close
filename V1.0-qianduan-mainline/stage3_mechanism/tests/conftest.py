"""pytest 配置：设置 PYTHONPATH，使 src/ 可导入。"""
import sys
from pathlib import Path

# 确保 src/ 在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
