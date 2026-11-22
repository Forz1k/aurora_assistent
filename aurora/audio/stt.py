from functools import lru_cache

from aurora.audio.input import RATE, SAMPLES, capture


@lru_cache(maxsize=1)
def load_model():
    from faster_whisper import WhisperModel

    return WhisperModel("base", device="cpu", compute_type="int8")


def transcribe(pcm: bytes) -> str:
    import numpy as np

    segments, _ = load_model().transcribe(np.frombuffer(pcm, dtype=np.float32), language="ru",
                                   condition_on_previous_text=False)
    return " ".join(part for segment in segments if (part := segment.text.strip()))


def recognize_command(device: int | None, seconds: int, notify=None) -> str:
    if notify:
        notify("LISTENING")
    else:
        print(f"Произнесите команду. Запись: {seconds} с.", flush=True)
    frames = list(capture(device, (seconds * RATE + SAMPLES - 1) // SAMPLES))
    if not any(frame.speech_probability >= 0.5 for frame in frames):
        if notify:
            raise ValueError("Речь не обнаружена.")
        return "Речь не обнаружена."
    if notify:
        notify("TRANSCRIBING")
    try:
        text = transcribe(b"".join(frame.pcm for frame in frames))
    except Exception as error:
        raise RuntimeError(f"Не удалось выполнить распознавание: {error}") from error
    if notify and not text:
        raise ValueError("Команду распознать не удалось.")
    return text or "Команду распознать не удалось."
