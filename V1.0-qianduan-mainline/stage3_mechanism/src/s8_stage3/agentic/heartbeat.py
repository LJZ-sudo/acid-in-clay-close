"""Liveness / progress heartbeat for the Stage 3 agent (Tier 3 / v2 capability).

Lets a long-running agent emit progress beats and lets a supervisor detect a
stall (no progress within ``stall_seconds``). The clock is injectable so the
behaviour is deterministic and testable; in production it defaults to
``time.monotonic``. This records runtime telemetry only — no scientific
evidence and no wall-clock timestamps written into result artifacts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

_VALID_STATUS = {"running", "ok", "error", "done"}


@dataclass
class Beat:
    seq: int
    step: str
    status: str
    t: float
    detail: str = ""


class Heartbeat:
    def __init__(self, clock: Callable[[], float] = time.monotonic, stall_seconds: float = 300.0):
        self._clock = clock
        self._stall_seconds = float(stall_seconds)
        self._beats: List[Beat] = []
        self._seq = 0

    def beat(self, step: str, status: str = "running", detail: str = "") -> Beat:
        status = status if status in _VALID_STATUS else "running"
        b = Beat(seq=self._seq, step=str(step), status=status, t=float(self._clock()), detail=str(detail))
        self._beats.append(b)
        self._seq += 1
        return b

    def last(self) -> Optional[Beat]:
        return self._beats[-1] if self._beats else None

    def seconds_since_last(self, now: Optional[float] = None) -> Optional[float]:
        last = self.last()
        if last is None:
            return None
        now = self._clock() if now is None else now
        return float(now) - last.t

    def is_stalled(self, now: Optional[float] = None) -> bool:
        last = self.last()
        if last is None:
            return False
        if last.status in ("done", "error"):
            return False
        gap = self.seconds_since_last(now)
        return gap is not None and gap > self._stall_seconds

    def report(self, now: Optional[float] = None) -> Dict[str, Any]:
        last = self.last()
        return {
            "n_beats": len(self._beats),
            "last_step": last.step if last else None,
            "last_status": last.status if last else None,
            "seconds_since_last": self.seconds_since_last(now),
            "stall_seconds": self._stall_seconds,
            "stalled": self.is_stalled(now),
        }
