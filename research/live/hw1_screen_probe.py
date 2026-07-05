# -*- coding: utf-8 -*-
"""HW-1 GUI 就绪截屏核验（§11.2-B,安全护栏 §11.1-3）。

只读截屏(不接管鼠标/键盘)。保存全屏 PNG + 缩略图,供 Agent 读图判断 CHI 是否在前台/就绪。
也尝试用 OpenCV 对 controllers/templates/ 下的关键模板做匹配,给出置信度参考。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import ImageGrab, Image

REPO = next(_p for _p in Path(__file__).resolve().parents if _p.name == "research").parent
MAIN = REPO / "V1.0-qianduan-mainline"
OUT = MAIN / "output" / "b_track_real"
TEMPLATE_DIR = MAIN / "stage0_measurement" / "controllers" / "templates"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"task": "HW-1 screen readiness probe",
           "at": datetime.now(timezone.utc).astimezone().isoformat()}
    img = ImageGrab.grab()
    full = OUT / "hw1_screen_full.png"
    img.save(full)
    # 缩略图(读图更省 token)
    thumb = img.copy()
    thumb.thumbnail((1280, 1280))
    thumb_path = OUT / "hw1_screen_thumb.png"
    thumb.save(thumb_path)
    rec["screen_size"] = list(img.size)
    rec["full_png"] = str(full)
    rec["thumb_png"] = str(thumb_path)

    # 模板匹配参考(置信度;低不代表一定不可用,仅供参考)
    try:
        import cv2
        shot = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        matches = {}
        for name in ("open_CHI.png", "start_to_measure.png", "save_as.png"):
            tp = TEMPLATE_DIR / name
            if not tp.exists():
                matches[name] = None
                continue
            tmpl = cv2.imread(str(tp))
            if tmpl is None:
                matches[name] = None
                continue
            res = cv2.matchTemplate(shot, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            matches[name] = {"max_confidence": round(float(max_val), 4),
                             "loc": [int(max_loc[0]), int(max_loc[1])]}
        rec["template_matches"] = matches
    except Exception as e:
        rec["template_matches_error"] = repr(e)

    (OUT / "hw1_screen_probe.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[HW-1] 截屏 {rec['screen_size']} → {thumb_path}")
    if rec.get("template_matches"):
        for k, v in rec["template_matches"].items():
            print(f"  template {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
