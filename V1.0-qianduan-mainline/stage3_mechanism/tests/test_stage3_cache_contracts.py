# -*- coding: utf-8 -*-
from __future__ import annotations


def test_stage3_cache_defaults_to_current(monkeypatch):
    monkeypatch.delenv("STAGE3_CACHE_DIR", raising=False)

    from s8_stage3.config.settings import Stage3Settings

    settings = Stage3Settings()
    parts = settings.cache_dir.parts

    assert parts[-3:] == ("data", "cache", "current")


def test_stage3_cache_dir_can_be_explicitly_overridden(monkeypatch, tmp_path):
    override = tmp_path / "run_specific_cache"
    monkeypatch.setenv("STAGE3_CACHE_DIR", str(override))

    from s8_stage3.config.settings import Stage3Settings

    settings = Stage3Settings()

    assert settings.cache_dir == override
