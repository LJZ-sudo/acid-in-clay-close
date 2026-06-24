# -*- coding: utf-8 -*-
"""科学记忆 SQLite schema（M5-B）。

表:
  nodes              证据/主张/参数节点(EVIDENCE/CLAIM/PARAMETER),带 valid 标志
  edges              supports/refutes/depends_on/invalidates/derived_from,supports/refutes 带 support_set_id
  claim_status       每主张当前四值状态 (support, refute, status, affected)
  claim_versions     主张状态版本历史(可审计:何时因何降级)
  invalidation_events 失效事件账本(证据 id + 原因 + 时间)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    node_type   TEXT NOT NULL,         -- EVIDENCE | CLAIM | PARAMETER
    label       TEXT,
    valid       INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT,
    meta        TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    src            TEXT NOT NULL,
    dst            TEXT NOT NULL,
    edge_type      TEXT NOT NULL,      -- supports | refutes | depends_on | invalidates | derived_from
    support_set_id TEXT,               -- 仅 supports/refutes:同一最小支持集共享
    meta           TEXT,
    FOREIGN KEY (src) REFERENCES nodes(id),
    FOREIGN KEY (dst) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS claim_status (
    claim_id    TEXT PRIMARY KEY,
    support     INTEGER NOT NULL DEFAULT 0,
    refute      INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'UNKNOWN',
    affected    INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT,
    FOREIGN KEY (claim_id) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS claim_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id    TEXT NOT NULL,
    support     INTEGER,
    refute      INTEGER,
    status      TEXT,
    affected    INTEGER,
    at          TEXT,
    cause       TEXT
);

CREATE TABLE IF NOT EXISTS invalidation_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id TEXT NOT NULL,
    reason      TEXT,
    at          TEXT
);

CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src, edge_type);
"""


def connect(db_path: Union[str, Path] = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(_SCHEMA)
    return conn
