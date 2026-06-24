# -*- coding: utf-8 -*-
"""RO-Crate 复现包生成器（WP5 / 投稿工程）。

按 RO-Crate 1.1 约定把"数据 + 代码 + 配置 + 证书 + 图快照 + 报告"打包成可交换、可复算的
研究对象:产出 `ro-crate-metadata.json`,逐文件记 sha256 + 类型 + 描述。
只读收集(不复制大文件;清单含相对路径 + 哈希,接收方按哈希校验)。诚实:只登记**真实存在**
的文件,缺失的标 `present:false`,绝不伪造产物。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_ro_crate(
    root: str | Path,
    artifacts: List[Dict[str, str]],
    out_path: str | Path,
    *,
    name: str = "Proton-conductor agentic discovery — reproducibility crate",
    description: str = "Evidence-governed semi-closed-loop discovery: code, configs, certs, reports.",
) -> Dict[str, Any]:
    """生成 ro-crate-metadata.json。

    artifacts: [{"path": 相对 root 的路径, "type": "File"|"Dataset", "desc": "..."}]
    返回写入的 metadata dict;每个 file entity 含 contentSize / sha256 / present。
    """
    root = Path(root)
    now = datetime.now(timezone.utc).astimezone().isoformat()
    graph: List[Dict[str, Any]] = [
        {"@type": "CreativeWork", "@id": "ro-crate-metadata.json",
         "conformsTo": {"@id": "https://w3id.org/ro/crate/1.1"},
         "about": {"@id": "./"}},
        {"@type": "Dataset", "@id": "./", "name": name, "description": description,
         "datePublished": now, "hasPart": [{"@id": a["path"]} for a in artifacts]},
    ]
    n_present = 0
    for a in artifacts:
        p = root / a["path"]
        sha = _sha256_file(p)
        present = sha is not None
        if present:
            n_present += 1
        graph.append({
            "@type": a.get("type", "File"),
            "@id": a["path"],
            "description": a.get("desc", ""),
            "present": present,
            "sha256": sha,
            "contentSize": (p.stat().st_size if present else None),
        })
    metadata = {"@context": "https://w3id.org/ro/crate/1.1/context", "@graph": graph,
                "_summary": {"n_artifacts": len(artifacts), "n_present": n_present,
                             "generated_at": now}}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


# 默认要打包的关键产物(相对主线根 V1.0-qianduan-mainline/)
DEFAULT_ARTIFACTS: List[Dict[str, str]] = [
    {"path": "configs/objective_registry.yaml", "type": "File", "desc": "目标函数注册表(冻结)"},
    {"path": "configs/dataset_registry.yaml", "type": "File", "desc": "数据集注册表(15/13 口径)"},
    {"path": "configs/evidence_admission_v2.yaml", "type": "File", "desc": "证据准入策略 v2"},
    {"path": "configs/terminology_aliases.yaml", "type": "File", "desc": "术语别名(命名降温)"},
    {"path": "scripts/reports/direct_hardware_call_report.json", "type": "File",
     "desc": "硬件写路径审计(autonomous_bypass=0)"},
    {"path": "stage1_optimization/campaign_memory/history_db_attapulgite.json", "type": "Dataset",
     "desc": "线 B 真实 trial 历史"},
]


def build_default_crate(mainline_root: str | Path) -> Dict[str, Any]:
    root = Path(mainline_root)
    return build_ro_crate(root, DEFAULT_ARTIFACTS, root / "scripts" / "reports" / "ro-crate-metadata.json")


if __name__ == "__main__":
    md = build_default_crate(Path(__file__).resolve().parents[2])
    print(json.dumps(md["_summary"], ensure_ascii=False))
