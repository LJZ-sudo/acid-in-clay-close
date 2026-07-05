# -*- coding: utf-8 -*-
"""M0 版本化基础设施。

职责:
1. 统一版本常量 + 从 configs/ 读策略并计算 sha256(可追溯)。
2. `make_provenance()`: 任何 v2 产物都带"分析版本 + 配置哈希 + git commit"。
3. `write_delta_report()`: legacy 与 v2 对照,绝不覆盖 legacy。
4. `freeze_legacy_manifest()`: 只读记录 legacy 产物的 sha256(冻结基线)。

所有路径用 Path(__file__) 相对解析,可移植(遵循 AGENTS.md 路径卫生)。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ---- 路径锚点(可移植) -------------------------------------------------- #
THIS_FILE = Path(__file__).resolve()
NDA_ROOT = THIS_FILE.parents[3] / "research"    # research/（输入输出 home）
DATA_ROOT = NDA_ROOT / "data"                   # research/data/（lineA_*/lineB_* 数据集）
RESULTS_ROOT = NDA_ROOT / "results"             # research/results/（v2 分析产物）
REPO_ROOT = THIS_FILE.parents[3]                # 仓库根
MAINLINE_ROOT = REPO_ROOT / "V1.0-qianduan-mainline"
CONFIGS_DIR = MAINLINE_ROOT / "configs"

# ---- 顶层版本常量(与 configs/*.yaml 的 *_version 字段对应) ------------- #
ANALYSIS_VERSION = "stage0-eis-v2.0.0"
ADMISSION_POLICY_VERSION = "evidence-policy-v2.0.0"
OBJECTIVE_REGISTRY_VERSION = "objective-registry-v2.0.0"
RB_METHOD_POLICY_VERSION = "rb-method-v2.0.0"

_CONFIG_FILES = {
    "stage0_v2_policy": "stage0_v2_policy.yaml",
    "rb_method_policy": "rb_method_policy.yaml",
    "evidence_admission_v2": "evidence_admission_v2.yaml",
    "objective_registry": "objective_registry.yaml",
}


# ---- 哈希工具 ----------------------------------------------------------- #
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> Optional[str]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    return sha256_bytes(p.read_bytes())


def sha256_obj(obj: Any) -> str:
    """对任意可 JSON 化对象做稳定哈希(键排序 + 紧凑分隔符)。"""
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(payload.encode("utf-8"))


# ---- 配置加载(带哈希) -------------------------------------------------- #
def load_config(name: str) -> Dict[str, Any]:
    """读取 configs/<name>.yaml,返回 dict 并注入 `_sha256` / `_path`。

    name 取自 _CONFIG_FILES 的键(如 'objective_registry')。
    """
    if name not in _CONFIG_FILES:
        raise KeyError(f"unknown config '{name}', expected one of {list(_CONFIG_FILES)}")
    import yaml  # 局部导入,避免无 yaml 环境下 import versions 即失败

    path = CONFIGS_DIR / _CONFIG_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"config not found: {path}")
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8")) or {}
    data["_sha256"] = sha256_bytes(raw)
    data["_path"] = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
    return data


def config_hashes() -> Dict[str, Optional[str]]:
    """所有 config 文件的 sha256(缺失则 None)。"""
    return {name: sha256_file(CONFIGS_DIR / fn) for name, fn in _CONFIG_FILES.items()}


# ---- git 锚点(best-effort) --------------------------------------------- #
def git_commit(short: bool = True) -> Optional[str]:
    args = ["git", "rev-parse", "--short", "HEAD"] if short else ["git", "rev-parse", "HEAD"]
    try:
        out = subprocess.run(args, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=10)
        if out.returncode == 0:
            return out.stdout.strip() or None
    except Exception:
        return None
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


# ---- 溯源块(所有 v2 产物统一携带) ------------------------------------- #
def make_provenance(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    prov: Dict[str, Any] = {
        "analysis_version": ANALYSIS_VERSION,
        "admission_policy_version": ADMISSION_POLICY_VERSION,
        "objective_registry_version": OBJECTIVE_REGISTRY_VERSION,
        "rb_method_policy_version": RB_METHOD_POLICY_VERSION,
        "config_sha256": config_hashes(),
        "git_commit": git_commit(),
        "generated_at": now_iso(),
    }
    if extra:
        prov.update(extra)
    return prov


# ---- delta_report:legacy vs v2 对照(绝不覆盖 legacy) ------------------ #
def write_delta_report(
    legacy: Dict[str, Any],
    v2: Dict[str, Any],
    out_path: str | Path,
    reason: str,
    key_fields: Optional[Iterable[str]] = None,
) -> Path:
    """生成 legacy 与 v2 的差异报告。

    key_fields 给定时逐字段比较数值差;否则只记录两侧顶层键。
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    diffs: List[Dict[str, Any]] = []
    if key_fields:
        for k in key_fields:
            lv, vv = legacy.get(k), v2.get(k)
            entry: Dict[str, Any] = {"field": k, "legacy": lv, "v2": vv}
            if isinstance(lv, (int, float)) and isinstance(vv, (int, float)):
                entry["abs_delta"] = float(vv) - float(lv)
                entry["changed"] = abs(entry["abs_delta"]) > 1e-12
            else:
                entry["changed"] = lv != vv
            diffs.append(entry)
    report = {
        "reason_for_delta": reason,
        "provenance": make_provenance(),
        "legacy_keys": sorted(legacy.keys()),
        "v2_keys": sorted(v2.keys()),
        "field_diffs": diffs,
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ---- legacy 冻结清单:只读记录 sha256(防被悄悄改写) -------------------- #
# 这些是"已发表/冻结"产物,v2 绝不覆盖;清单用于事后核验它们未被改动。
DEFAULT_LEGACY_PRODUCTS = [
    "V1.0-qianduan-mainline/stage1_optimization/campaign_memory/history_db_attapulgite.json",
    "research/prospective/line_B_mobo_closed_loop/official_recipe.json",
]


def freeze_legacy_manifest(
    extra_paths: Optional[Iterable[str]] = None,
    out_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """记录 legacy 产物的 sha256 + 大小 + mtime(只读,不改动任何文件)。

    默认把 research 下所有 lineA_*/lineB_* 的 aggregated/arrhenius
    也纳入(它们是本轮分析的输入,需冻结基线)。
    """
    products: List[str] = list(DEFAULT_LEGACY_PRODUCTS)
    for pat in ("lineA_*", "lineB_*"):
        for d in sorted(DATA_ROOT.glob(pat)):
            for fn in ("aggregated_results.json", "arrhenius_analysis.json"):
                fp = d / fn
                if fp.exists():
                    products.append(str(fp.relative_to(REPO_ROOT)))
    if extra_paths:
        products.extend(extra_paths)

    entries: Dict[str, Any] = {}
    for rel in products:
        ap = (REPO_ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if ap.exists() and ap.is_file():
            st = ap.stat()
            entries[rel] = {
                "sha256": sha256_file(ap),
                "size_bytes": st.st_size,
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }
        else:
            entries[rel] = {"sha256": None, "missing": True}

    manifest = {
        "purpose": "legacy freeze baseline (read-only); v2 must never overwrite these",
        "provenance": make_provenance(),
        "n_products": len(entries),
        "products": entries,
    }
    if out_path is None:
        out_path = THIS_FILE.parent / "legacy_freeze_manifest.json"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    # 自检 + 生成 legacy 冻结清单
    print("[stage0_v2.versions] provenance:")
    print(json.dumps(make_provenance(), ensure_ascii=False, indent=2))
    m = freeze_legacy_manifest()
    print(f"\n[stage0_v2.versions] froze {m['n_products']} legacy products -> "
          f"stage0_v2/legacy_freeze_manifest.json")
