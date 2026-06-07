#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stage0 Wrapper Script - Fixes encoding issues

Wrapper around stage0_measurement/run_offline.py to handle encoding problems
"""

import os
import sys
from pathlib import Path

# Set UTF-8 encoding for stdout/stderr
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Repo root: .../V1.0-qianduan-mainline (this file lives in code/stage0_processing/)
project_root = Path(__file__).resolve().parent.parent.parent
stage0_dir = project_root / "stage0_measurement"
sys.path.insert(0, str(stage0_dir))

# Import and run
if __name__ == "__main__":
    # Remove wrapper script from argv
    sys.argv = [str(stage0_dir / "run_offline.py")] + sys.argv[1:]
    
    # Change to stage0 directory
    os.chdir(str(stage0_dir))
    
    # Import and execute
    import run_offline
    sys.exit(run_offline.main())
