# -*- coding: utf-8 -*-
"""WP0 / P0-4：LLMCallBundle 落盘 + 公开哈希 + 可选真实加密。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

MAINLINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MAINLINE / "stage1_optimization"))

from agents.prompt_envelope import LLMCallBundle, write_llm_call_bundle  # noqa: E402


def _bundle() -> LLMCallBundle:
    return LLMCallBundle(
        bundle_id="test-bundle-0001",
        created_at=datetime.now(timezone.utc).astimezone().isoformat(),
        model="openai/gpt-5.4", provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        temperature=0.0, max_tokens=8000, timeout=240, retry_count=0,
        parser_version="next_experiment_schema@0.2.0",
        messages=[{"role": "system", "content": "careful planner"},
                  {"role": "user", "content": "suggest next R/N given 10 trials"}],
        structured_output={"R": 0.28, "N": 0.96},
        raw_response_text='{"R":0.28,"N":0.96}',
        envelope={"model": "openai/gpt-5.4"},
    )


def test_plaintext_write_and_public_hash(tmp_path):
    b = _bundle()
    res = write_llm_call_bundle(b, tmp_path)            # 无 key → 明文
    assert res["encrypted"] is False
    assert res["sha256"] == b.content_sha256()
    body = Path(res["path"])
    assert body.exists() and body.suffix == ".json"
    sidecar = json.loads((tmp_path / f"{b.bundle_id}.sha256.json").read_text(encoding="utf-8"))
    assert sidecar["content_sha256"] == b.content_sha256()
    assert sidecar["encrypted"] is False


def test_encrypted_write_roundtrip(tmp_path):
    pytest.importorskip("cryptography")
    import base64, hashlib
    from cryptography.fernet import Fernet
    b = _bundle()
    res = write_llm_call_bundle(b, tmp_path, encrypt_key="secret-passphrase")
    assert res["encrypted"] is True
    enc_path = Path(res["path"])
    assert enc_path.suffix == ".enc"
    # 真实可解密回原文(证明不是假装加密)
    key = base64.urlsafe_b64encode(hashlib.sha256(b"secret-passphrase").digest())
    decrypted = Fernet(key).decrypt(enc_path.read_bytes()).decode("utf-8")
    assert json.loads(decrypted)["structured_output"] == {"R": 0.28, "N": 0.96}
    # 公开 sidecar 仍只含哈希,且与明文哈希一致
    sidecar = json.loads((tmp_path / f"{b.bundle_id}.sha256.json").read_text(encoding="utf-8"))
    assert sidecar["content_sha256"] == b.content_sha256()
    assert sidecar["encrypted"] is True
