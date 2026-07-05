# -*- coding: utf-8 -*-
"""等腔体回温到起测温度:轮询 /api/control/status,到温后打印 READY_TO_START 哨兵退出。"""
import json
import time
import urllib.request

URL = "http://127.0.0.1:8000/api/control/status"
TARGET_C = 18.5

while True:
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:
            s = json.loads(r.read().decode("utf-8"))
        t = s.get("temperature")
        print(f"chamber_T={t} running={s.get('running')}", flush=True)
        if t is not None and float(t) >= TARGET_C:
            print("READY_TO_START", flush=True)
            break
    except Exception as exc:
        print(f"poll error: {exc}", flush=True)
    time.sleep(120)
