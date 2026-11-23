"""Локальная русская озвучка Silero. Текст поступает через stdin в UTF-8."""

import argparse
import math
import re
import sqlite3
import sys
from contextlib import ExitStack
import textwrap
from pathlib import Path

from aurora.tts import design, natural
from aurora.tts.cache import AudioCache

MODEL = Path(__file__).resolve().parents[2] / "data/voices/v5_6_ru.pt"
RATE = 48000
QWEN_ENGINES = {natural.SPEAKER: natural, design.SPEAKER: design}
VOICES = {natural.SPEAKER: "Аврора · живая речь", design.SPEAKER: "Аврора · разговорный", "xenia": "Ксения · Xenia", "kseniya": "Ксения · Kseniya", "baya": "Бая"}
DEFAULT_VOICE = "xenia"


def passages(text, limit=450):
    # Оставляем соседние фразы вместе для интонации, ограничиваем длину для модели.
    for paragraph in text.splitlines():
        group = ""
        for sentence in re.split(r"(?<=[.!?…])\s+", paragraph.strip()):
            for part in textwrap.wrap(sentence, width=limit, break_on_hyphens=False):
                if group and len(group) + len(part) + 1 > limit:
                    yield group
                    group = ""
                group = f"{group} {part}".strip()
        if group:
            yield group


def load_voice():
    import torch

    if not MODEL.is_file():
        raise FileNotFoundError("Загрузите русскую модель Silero v5_6_ru по инструкции в README.")
    torch.set_num_threads(6)
    return torch.package.PackageImporter(str(MODEL)).load_pickle("tts_models", "model")


def synthesize(model, text, speaker):
    import torch

    with torch.inference_mode():
        for part in passages(text):
            audio = model.apply_tts(text=part, speaker=speaker, sample_rate=RATE)
            yield audio.clamp(-1, 1).mul(32767).short().numpy().tobytes()


def render(text, speaker, cache):
    primary = backup = None
    fallback = False
    engine = QWEN_ENGINES.get(speaker)
    rate = engine.RATE if engine else RATE
    profile = engine.PROFILE if engine else f"silero-v5_6_ru:{speaker}:{RATE}"
    for part in passages(text, 180 if engine else 450):
        try:
            pcm = cache.get(profile, part) if cache else None
        except sqlite3.Error:
            pcm = None
        if pcm:
            yield rate, pcm
            continue
        if not fallback:
            try:
                if primary is None:
                    primary = engine.load_model() if engine else load_voice()
                if engine:
                    pcm = engine.synthesize(primary, part)
                else:
                    pcm = b"".join(synthesize(primary, part, speaker))
                if not pcm:
                    raise ValueError("Пустой результат синтеза")
            except Exception:
                print("AURORA_PIPER_FALLBACK", flush=True)
                fallback = True
        if fallback:
            from piper import PiperVoice

            if backup is None:
                backup = PiperVoice.load(MODEL.with_name("ru_RU-irina-medium.onnx"), use_cuda=False)
            for chunk in backup.synthesize(part):
                yield backup.config.sample_rate, chunk.audio_int16_bytes
            continue
        if cache:
            try:
                cache.put(profile, part, pcm)
            except sqlite3.Error:
                pass
        yield rate, pcm


def speak(text, speaker=DEFAULT_VOICE):
    import sounddevice as sd

    with ExitStack() as resources:
        try:
            cache = AudioCache(MODEL.parents[1] / "tts-cache.sqlite3")
            resources.callback(cache.db.close)
        except (OSError, sqlite3.Error):
            cache = None
        output = None
        previous_rate = None
        with ExitStack() as playback:
            for rate, pcm in render(text, speaker, cache):
                if rate != previous_rate:
                    playback.close()
                    output = playback.enter_context(sd.RawOutputStream(
                        samplerate=rate, channels=1, dtype="int16", latency="low"))
                    previous_rate = rate
                # Short writes to a low-latency stream pace the meter with playback.
                block_bytes = max(1, rate // 25) * 2
                for start in range(0, len(pcm), block_bytes):
                    block = memoryview(pcm)[start:start + block_bytes]
                    samples = block.cast("h")
                    rms = math.sqrt(sum(x * x for x in samples) / len(samples))
                    level = min(10, round(max(0, rms - 150) / 450))
                    output.write(block)
                    print(f"AURORA_MOUTH {level}", flush=True)
                print("AURORA_MOUTH 0", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speaker", choices=VOICES, default=DEFAULT_VOICE)
    args = parser.parse_args()
    try:
        speak(sys.stdin.buffer.read().decode("utf-8"), args.speaker)
    except Exception as error:
        sys.stdout.buffer.write(str(error).encode("utf-8", errors="replace"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
