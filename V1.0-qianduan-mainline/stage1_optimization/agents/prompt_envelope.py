# -*- coding: utf-8 -*-
"""Prompt 溯源信封（M2-5 / G6）。

GPT/GPT-2 指出:现有 LLM 溯源只存 system/user_prompt_sha256，"可验证完整性 ≠ 可重复生成"。
本模块在**不公开 prompt 原文**的前提下,捕获足以重建来源的元数据:
  - 模板 git commit + system/user 模板各自 sha256（→ 知道用的哪版模板)
  - 输入产物哈希列表(→ 知道喂了哪些数据)
  - 渲染后 prompt 的 sha256(→ 完整性校验)
  - 模型 / 温度 / 响应 sha256 / 重试次数(→ 调用条件)

加性纯函数,不改写冻结闭环;供 strategy_planner / llm_client 旁路记录。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

MAINLINE_ROOT = Path(__file__).resolve().parents[2]


def _sha256_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(MAINLINE_ROOT), capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


@dataclass
class PromptEnvelope:
    template_git_commit: Optional[str]
    system_template_sha256: Optional[str]
    user_template_sha256: Optional[str]
    input_artifact_hashes: List[str] = field(default_factory=list)
    rendered_prompt_sha256: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    response_sha256: Optional[str] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_prompt_envelope(
    *,
    system_template: Optional[str] = None,
    user_template: Optional[str] = None,
    rendered_system: Optional[str] = None,
    rendered_user: Optional[str] = None,
    input_artifacts: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    response_text: Optional[str] = None,
    retry_count: int = 0,
    git_commit: Optional[str] = None,
) -> PromptEnvelope:
    """从模板 + 输入构造 PromptEnvelope（不保存原文,只存可重建来源的指纹）。

    input_artifacts: {name: obj}，每个 obj 做稳定 JSON 哈希后记 "name:sha8…"。
    rendered_*: 实际发送的 system/user 文本（仅用于算 rendered_prompt_sha256,不落库)。
    """
    input_hashes: List[str] = []
    for name, obj in (input_artifacts or {}).items():
        try:
            payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            payload = str(obj)
        input_hashes.append(f"{name}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}")

    rendered = (rendered_system or "") + "\x00" + (rendered_user or "")
    rendered_sha = _sha256_text(rendered) if (rendered_system or rendered_user) else None

    return PromptEnvelope(
        template_git_commit=git_commit if git_commit is not None else _git_commit(),
        system_template_sha256=_sha256_text(system_template),
        user_template_sha256=_sha256_text(user_template),
        input_artifact_hashes=input_hashes,
        rendered_prompt_sha256=rendered_sha,
        model=model,
        temperature=temperature,
        response_sha256=_sha256_text(response_text),
        retry_count=retry_count,
    )


@dataclass
class LLMCallBundle:
    """完整 LLM 调用包（P0-4 / G6）。

    GPT-3 指出:只存 prompt 哈希无法重现 LLM 决策。本结构保存**实际输入消息、结构化输出、
    模型/provider/温度/重试/解析器版本**;落盘时:
      - 公开侧只发布 content_sha256(可入库),正文受 LLM_BUNDLE_KEY 加密(Fernet)或本地明文(不入库)。
    诚实边界:`temperature=0.0` 与哈希都只保证"低随机 + 完整性",不保证 provider 端逐字节可复现。
    """
    bundle_id: str
    created_at: str
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    parser_version: Optional[str] = None
    messages: List[Dict[str, str]] = field(default_factory=list)
    structured_output: Optional[Dict[str, Any]] = None
    raw_response_text: Optional[str] = None
    envelope: Optional[Dict[str, Any]] = None

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def content_sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _fernet_from_passphrase(passphrase: str):
    import base64
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
    return Fernet(key)


def write_llm_call_bundle(
    bundle: LLMCallBundle,
    out_dir: str | Path,
    encrypt_key: Optional[str] = None,
) -> Dict[str, Any]:
    """落盘完整调用包,返回 {bundle_id, path, sha256, encrypted}。

    - encrypt_key 或环境变量 LLM_BUNDLE_KEY 存在 → Fernet 加密写 `<id>.json.enc`(encrypted=True)。
    - 否则明文写 `<id>.json`(encrypted=False;**正文不应入库,仅 sidecar 哈希可公开**)。
    - 始终写公开 sidecar `<id>.sha256.json`(只含 bundle_id/sha256/model/created_at/encrypted)。
    fail-safe:加密不可用时退回明文并显式标 encrypted=False,绝不假装已加密。
    """
    import os
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    content = bundle.canonical_json()
    sha = bundle.content_sha256()
    key = encrypt_key if encrypt_key is not None else os.environ.get("LLM_BUNDLE_KEY")

    encrypted = False
    if key:
        try:
            token = _fernet_from_passphrase(key).encrypt(content.encode("utf-8"))
            body_path = out / f"{bundle.bundle_id}.json.enc"
            body_path.write_bytes(token)
            encrypted = True
        except Exception:
            body_path = out / f"{bundle.bundle_id}.json"
            body_path.write_text(content, encoding="utf-8")
    else:
        body_path = out / f"{bundle.bundle_id}.json"
        body_path.write_text(content, encoding="utf-8")

    sidecar = {
        "bundle_id": bundle.bundle_id,
        "content_sha256": sha,
        "model": bundle.model,
        "created_at": bundle.created_at,
        "encrypted": encrypted,
    }
    (out / f"{bundle.bundle_id}.sha256.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"bundle_id": bundle.bundle_id, "path": str(body_path), "sha256": sha, "encrypted": encrypted}


if __name__ == "__main__":
    env = build_prompt_envelope(
        system_template="You are a careful planner.",
        user_template="Suggest next R/N given {history}.",
        rendered_system="You are a careful planner.",
        rendered_user="Suggest next R/N given 10 trials.",
        input_artifacts={"history_db": {"trials": 10}, "campaign": "attapulgite_aice"},
        model="openai/gpt-5.4", temperature=0.0,
        response_text='{"R":0.28,"N":0.96}', retry_count=0,
    )
    print(json.dumps(env.to_dict(), ensure_ascii=False, indent=2))
