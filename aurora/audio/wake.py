"""Локальный потоковый детектор отдельного обращения по имени."""

import json
from contextlib import closing
from pathlib import Path

import numpy as np

from aurora.audio.input import RATE, capture
from aurora.audio.stt import recognize_command

MODEL_NAME = "vosk-model-small-ru-0.22"


def make_detector():
    import vosk

    vosk.SetLogLevel(-1)
    path = Path(__file__).resolve().parents[2] / "data" / MODEL_NAME
    try:
        model = vosk.Model(str(path)) if path.is_dir() else vosk.Model(model_name=MODEL_NAME)
        grammar = json.dumps(["аврора", "[unk]"], ensure_ascii=False)
        detector = vosk.KaldiRecognizer(model, RATE, grammar)
        detector.SetWords(True)
        return detector
    except Exception as error:
        raise RuntimeError(f"Не удалось загрузить русскую модель Vosk: {error}") from error


def wait_for_name(frames, detector) -> bool:
    for frame in frames:
        samples = np.frombuffer(frame.pcm, dtype=np.float32)
        pcm = (samples.clip(-1, 1) * 32767).astype("<i2").tobytes()
        if detector.AcceptWaveform(pcm):
            words = json.loads(detector.Result()).get("result", [])
            if len(words) == 1 and words[0]["word"] == "аврора" and words[0]["conf"] >= 0.65:
                return True
    return False


def listen(device: int | None, seconds: int) -> str:
    detector = make_detector()
    with closing(capture(device, None)) as frames:
        print("Ожидаю имя «Аврора». Для выхода нажмите Ctrl+C.", flush=True)
        if not wait_for_name(frames, detector):
            raise RuntimeError("Поток микрофона завершился до активации.")
    return recognize_command(device, seconds)
