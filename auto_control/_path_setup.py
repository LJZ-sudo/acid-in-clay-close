from pathlib import Path
import sys


AUTO_CONTROL_DIR = Path(__file__).resolve().parent
CLOSE_ROOT = AUTO_CONTROL_DIR.parent
MODULES_DIR = AUTO_CONTROL_DIR / "modules"


def ensure_close_root() -> Path:
    """Ensure the close root is importable."""
    if str(CLOSE_ROOT) not in sys.path:
        sys.path.insert(0, str(CLOSE_ROOT))
    return CLOSE_ROOT


def ensure_auto_control_dir() -> Path:
    """Ensure auto_control itself is importable for direct script runs."""
    if str(AUTO_CONTROL_DIR) not in sys.path:
        sys.path.insert(0, str(AUTO_CONTROL_DIR))
    return AUTO_CONTROL_DIR


def ensure_modules_dir() -> Path:
    """Ensure auto_control/modules is importable for legacy fallbacks."""
    if str(MODULES_DIR) not in sys.path:
        sys.path.insert(0, str(MODULES_DIR))
    return MODULES_DIR
