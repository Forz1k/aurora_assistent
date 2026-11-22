from aurora.audio.input import RATE, SAMPLES, capture


def transcribe(pcm: bytes) -> str:
    import numpy as np
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(np.frombuffer(pcm, dtype=np.float32), language="ru",
                                   condition_on_previous_text=False)
    return " ".join(part for segment in segments if (part := segment.text.strip()))


def recognize_command(device: int | None, seconds: int) -> str:
    print(f"Произнесите команду. Запись: {seconds} с.", flush=True)
    frames = list(capture(device, (seconds * RATE + SAMPLES - 1) // SAMPLES))
    if not any(frame.speech_probability >= 0.5 for frame in frames):
        return "Речь не обнаружена."
    try:
        text = transcribe(b"".join(frame.pcm for frame in frames))
    except Exception as error:
        raise RuntimeError(f"Не удалось выполнить распознавание: {error}") from error
    return text or "Команду распознать не удалось."
