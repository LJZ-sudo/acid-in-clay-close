# -*- coding: utf-8 -*-
"""读取原始 EIS 谱(M1-1/M1-2/M1-5 共用)。

复用管线自带的 `chi_parser.parse_chi_file`,确保 freq/z_real/z_imag 的符号约定
与 legacy Stage0 完全一致(不自造解析器,避免约定漂移)。

aggregated_results.json 的每个 measurement 带绝对 `filepath` 指向原始 txt;
但这些路径可能是别的机器留下的(C:\\Users\\JZ\\...)。本模块按 AGENTS.md 路径卫生,
优先用 basename 在本机的 data/新材料 下重新定位。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .versions import MAINLINE_ROOT

# 让 chi_parser 可导入(它在 stage0_measurement 下,用 sys.path 注入)
_STAGE0_DIR = MAINLINE_ROOT / "stage0_measurement"
if str(_STAGE0_DIR) not in sys.path:
    sys.path.insert(0, str(_STAGE0_DIR))

from modules.io_utils.chi_parser import parse_chi_file  # noqa: E402

_DATA_NEW_MATERIALS = MAINLINE_ROOT / "data" / "新材料"
_DATA_ROOT = MAINLINE_ROOT / "data"


def _relocate_filepath(orig: str) -> Optional[Path]:
    """把 aggregated 里(可能跨机器)的绝对路径重定位到本机 data 下。

    策略:① 原路径存在直接用;② 按 basename 在 data/新材料 递归找;③ 在 data 递归找。
    """
    if not orig:
        return None
    p = Path(orig)
    if p.exists():
        return p
    base = p.name
    for root in (_DATA_NEW_MATERIALS, _DATA_ROOT):
        if root.exists():
            hits = list(root.rglob(base))
            if hits:
                return hits[0]
    return None


def load_spectrum(filepath: str) -> Optional[Dict[str, np.ndarray]]:
    """读单条原始谱 → {freq, z_real, z_imag}(失败返回 None)。"""
    fp = _relocate_filepath(filepath)
    if fp is None:
        return None
    res = parse_chi_file(str(fp))
    if not res.get("success"):
        return None
    return {
        "freq": np.asarray(res["frequencies"], dtype=float),
        "z_real": np.asarray(res["z_real"], dtype=float),
        "z_imag": np.asarray(res["z_imag"], dtype=float),
        "resolved_path": str(fp),
    }


def load_dataset_points(aggregated_json: str | Path) -> List[Dict[str, Any]]:
    """读 aggregated_results.json,返回每个测点的 (温度 + legacy 摘要 + 原始谱)。

    只返回原始谱可成功加载的点;每个元素:
      {temperature_C, temperature_K, status, kk_warning, kk_mu_median,
       rb_ohm_legacy, rb_method_legacy, conductivity_legacy, success_legacy,
       freq, z_real, z_imag, resolved_path}
    """
    aggregated_json = Path(aggregated_json)
    data = json.loads(aggregated_json.read_text(encoding="utf-8"))
    out: List[Dict[str, Any]] = []
    for m in data.get("measurements", []) or []:
        spec = load_spectrum(m.get("filepath", ""))
        if spec is None:
            continue
        out.append({
            "filepath": m.get("filepath"),
            "resolved_path": spec["resolved_path"],
            "temperature_C": m.get("temperature_C"),
            "temperature_K": m.get("temperature_K"),
            "status": m.get("status"),
            "kk_warning": bool(m.get("kk_warning")),
            "kk_mu_median": m.get("kk_mu_median"),
            "kk_mu_max": m.get("kk_mu_max"),
            "rb_ohm_legacy": m.get("rb_ohm"),
            "rb_method_legacy": m.get("rb_method"),
            "conductivity_legacy": m.get("conductivity_S_per_cm"),
            "success_legacy": bool(m.get("success")),
            "freq": spec["freq"],
            "z_real": spec["z_real"],
            "z_imag": spec["z_imag"],
        })
    return out


def discover_datasets(kind: str = "lineA") -> List[Path]:
    """列出 experiments/data 下含 aggregated_results.json 的数据集目录。"""
    from .versions import DATA_ROOT
    pat = "lineA_*" if kind == "lineA" else ("lineB_*" if kind == "lineB" else "*")
    out: List[Path] = []
    for d in sorted(DATA_ROOT.glob(pat)):
        if (d / "aggregated_results.json").exists():
            out.append(d)
    return out
