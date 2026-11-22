"""Захват моно PCM и потоковая оценка вероятности речи на CPU."""

from collections.abc import Iterator
from dataclasses import dataclass

import sounddevice as sd
from silero_vad_lite import SileroVAD

RATE = 16000
SAMPLES = 512


@dataclass(frozen=True)
class AudioFrame:
    pcm: bytes  # float32, моно, 16 кГц
    speech_probability: float


def microphones() -> list[str]:
    apis = sd.query_hostapis()
    return [
        f"{index}: {device['name']} ({apis[device['hostapi']]['name']})"
        for index, device in enumerate(sd.query_devices())
        if device["max_input_channels"] > 0
    ]


def capture(device: int | None, frames: int) -> Iterator[AudioFrame]:
    if device is not None and device < 0:
        raise ValueError("Номер микрофона должен быть неотрицательным.")
    vad = SileroVAD(RATE)
    with sd.RawInputStream(device=device, samplerate=RATE, channels=1,
                           dtype="float32", blocksize=SAMPLES) as stream:
        for _ in range(frames):
            block, overflow = stream.read(SAMPLES)
            if overflow:
                raise RuntimeError("Переполнение буфера микрофона. Повторите захват.")
            pcm = bytes(block)
            if len(pcm) != SAMPLES * 4:
                raise RuntimeError("Микрофон вернул неполный блок.")
            yield AudioFrame(pcm, vad.process(pcm))


def _diagnose(list_only: bool, device: int | None, seconds: int) -> int:
    if list_only:
        devices = microphones()
        print("\n".join(devices) if devices else "Нет доступных входных устройств.")
        return 0 if devices else 1
    count = (seconds * RATE + SAMPLES - 1) // SAMPLES
    speech_frames = 0
    print(f"Проверка микрофона, {seconds} с. Произнесите фразу.", flush=True)
    for frame in capture(device, count):
        speech_frames += frame.speech_probability >= 0.5
    print(f"Получено блоков: {count}. С речью: {speech_frames} ({speech_frames * SAMPLES / RATE:.2f} с).")
    return 0


def diagnose(list_only: bool, device: int | None, seconds: int) -> int:
    try:
        return _diagnose(list_only, device, seconds)
    except sd.PortAudioError as error:
        raise RuntimeError(f"Устройство недоступно: {error}") from error
