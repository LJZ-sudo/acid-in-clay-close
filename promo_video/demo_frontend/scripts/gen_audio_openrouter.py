"""Generate narration mp3 via OpenRouter's TTS endpoint (/audio/speech).

Uses the project's existing OpenRouter key (sk-or-...), so no separate OpenAI
account is needed. One-time generation: the mp3s are committed under
src/assets/audio/ and loaded by App.jsx — you do NOT regenerate every run.

Reads key + base URL from V1.0-qianduan-mainline/stage1_optimization/.env
(LLM_API_KEY / LLM_BASE_URL).

Usage:
    # one scene, a chosen model+voice (sample for A/B listening):
    python scripts/gen_audio_openrouter.py --only hook --model openai/gpt-4o-mini-tts \
        --voice nova --instructions "充满感染力的科技宣传片男声解说" --suffix _optB

    # all scenes with the picked model+voice:
    python scripts/gen_audio_openrouter.py --model google/gemini-3.1-flash-tts-preview --voice alloy
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import wave
from pathlib import Path

HERE = Path(__file__).resolve()
DEMO = HERE.parents[1]
OUT_DIR = DEMO / "src" / "assets" / "audio"
REPO = HERE.parents[3]
ENV = REPO / "V1.0-qianduan-mainline" / "stage1_optimization" / ".env"

# Keep in sync with App.jsx SCENES[].narration / gen_audio*.py NARRATION.
sys.path.insert(0, str(DEMO / "scripts"))


def load_narration(lang: str):
    if lang == "en":
        from gen_audio_en import NARRATION as N  # noqa: E402
    else:
        from gen_audio import NARRATION as N  # noqa: E402
    return N


def read_env() -> tuple[str, str]:
    key = base = ""
    for line in ENV.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^\s*([A-Za-z0-9_]+)\s*=\s*"?([^"\r\n]+)"?\s*$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip().strip('"')
        if k == "LLM_API_KEY":
            key = v
        elif k == "LLM_BASE_URL":
            base = v.rstrip("/")
    if not key:
        raise SystemExit(f"LLM_API_KEY not found in {ENV}")
    return key, base or "https://openrouter.ai/api/v1"


def pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def synth(scene_id: str, text: str, model: str, voice: str,
          instructions: str | None, suffix: str, fmt: str, key: str, base: str) -> None:
    url = f"{base}/audio/speech"
    body = {"model": model, "input": text, "voice": voice, "response_format": fmt}
    if instructions:
        body["instructions"] = instructions
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[HTTP {e.code}] {scene_id}: {e.read().decode('utf-8', 'ignore')[:500]}")
    if len(data) < 1024:
        raise SystemExit(f"[tiny output] {scene_id}: {data[:300]!r}")
    if fmt == "pcm":
        data = pcm_to_wav(data)
        ext = "wav"
    else:
        ext = "mp3"
    out = OUT_DIR / f"{scene_id}{suffix}.{ext}"
    out.write_bytes(data)
    print(f"  [ok] {out.name}  ({len(data)//1024} KB)  model={model} voice={voice}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-mini-tts")
    ap.add_argument("--voice", default="nova")
    ap.add_argument("--instructions", default=None)
    ap.add_argument("--only", default=None, help="single scene id; default = all")
    ap.add_argument("--suffix", default="", help="filename suffix, e.g. _optB for samples")
    ap.add_argument("--format", default="mp3", choices=["mp3", "pcm"],
                    help="pcm -> wrapped to wav locally (use for Gemini)")
    ap.add_argument("--lang", default="en", choices=["en", "zh"])
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    key, base = read_env()
    narration = load_narration(args.lang)
    print(f"base={base}  model={args.model}  voice={args.voice}  fmt={args.format}  lang={args.lang}  -> {OUT_DIR}")
    ids = [args.only] if args.only else list(narration.keys())
    for sid in ids:
        synth(sid, narration[sid], args.model, args.voice, args.instructions, args.suffix, args.format, key, base)


if __name__ == "__main__":
    main()
