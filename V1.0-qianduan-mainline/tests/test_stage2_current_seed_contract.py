# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED = PROJECT_ROOT / "stage2_statistics" / "exports" / "stage3_seed.json"


def test_current_stage2_seed_is_stage3_canonical_contract():
    seed = json.loads(SEED.read_text(encoding="utf-8"))

    assert seed["schema_version"] == "0.2.0"
    assert seed["source_system"] == "s8_reference"
    assert seed["source_mode"] == "retrospective"
    assert seed["stage3_ready"] is True
    assert seed["stage3_blocking_reasons"] == []
    assert seed["input_files"]
    assert seed["input_hashes"]
    assert len(seed["sample_summary"]) == 40
    assert len(seed["segment_fits"]) > 0
    assert len(seed["evidence_units"]) > 0

    digest = hashlib.sha256(SEED.read_bytes()).hexdigest()
    assert len(digest) == 64
