"""A/B sample generator: render the hook narration in several American
documentary-leaning edge-tts voices into src/assets/samples/ for listening.
Does NOT touch the live {id}.mp3 files."""
import asyncio
from pathlib import Path
import edge_tts
from gen_audio_en import NARRATION

OUT = Path(__file__).resolve().parents[1] / "src" / "assets" / "samples"
TEXT = NARRATION["hook"]
VOICES = [
    "en-US-GuyNeural",        # current (neutral newsreader)
    "en-US-SteffanNeural",    # deep, narration-oriented
    "en-US-BrianNeural",      # warm, natural
    "en-US-AndrewMultilingualNeural",  # warm, conversational
    "en-US-RogerNeural",      # mature, steady
]


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for v in VOICES:
        out = OUT / f"hook__{v}.mp3"
        try:
            await edge_tts.Communicate(TEXT, v, rate="-3%").save(str(out))
            print(f"  [ok] {out.name}  ({out.stat().st_size//1024} KB)")
        except Exception as e:  # noqa: BLE001
            print(f"  [FAIL] {v}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
