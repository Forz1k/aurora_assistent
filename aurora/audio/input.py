"""Захват моно PCM и потоковая оценка вероятности речи на CPU."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import count

import sounddevice as sd
from silero_vad_lite import SileroVAD

RATE = 16000
SAMPLES = 512


@dataclass(frozen=True)
class AudioFrame:
    pcm: bytes  # float32, моно, 16 кГц
    speech_probability: float


def input_devices() -> list[tuple[int, str, str]]:
    apis = sd.query_hostapis()
    aliases = {"microsoft sound mapper - input", "первичный драйвер записи звука",
               "primary sound capture driver"}
    groups = {}
    for index, device in enumerate(sd.query_devices()):
        name = device["name"]
        if device["max_input_channels"] and name.casefold() not in aliases:
            api = apis[device["hostapi"]]["name"]
            groups.setdefault(api, []).append((index, name, api))
    # Windows enumerates the same endpoints under multiple audio APIs.
    # Prefer the tested MME capture path and retain native PortAudio indices.
    for api in ("MME", "Windows WASAPI", "Windows DirectSound"):
        if api in groups:
            return groups[api]
    return next(iter(groups.values()), [])


def microphones() -> list[str]:
    return [f"{index}: {name} ({api})" for index, name, api in input_devices()]


def select_device(index, preferred):
    if index is not None or not preferred:
        return index
    matches = [i for i, name, _ in input_devices() if name.casefold() == preferred.casefold()]
    if len(matches) != 1:
        raise ValueError(f"Уточните вход через --list-mics и --device: {preferred}")
    return matches[0]


def capture(device: int | None, frames: int | None) -> Iterator[AudioFrame]:
    if device is not None and device < 0:
        raise ValueError("Номер микрофона должен быть неотрицательным.")
    vad = SileroVAD(RATE)
    with sd.RawInputStream(device=device, samplerate=RATE, channels=1,
                           dtype="float32", blocksize=SAMPLES) as stream:
        for _ in (count() if frames is None else range(frames)):
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
