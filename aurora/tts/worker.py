"""Озвучивание одного ответа. Текст поступает через stdin в UTF-8."""

import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[2] / "data/voices/ru_RU-irina-medium.onnx"


def speak(text: str) -> None:
    import sounddevice as sd
    from piper import PiperVoice

    if not MODEL.is_file() or not MODEL.with_suffix(".onnx.json").is_file():
        raise FileNotFoundError("Загрузите голос ru_RU-irina-medium по инструкции в README.")
    voice = PiperVoice.load(MODEL, use_cuda=False)
    with sd.RawOutputStream(samplerate=voice.config.sample_rate, channels=1, dtype="int16") as output:
        for chunk in voice.synthesize(text):
            output.write(chunk.audio_int16_bytes)


def main() -> int:
    try:
        speak(sys.stdin.buffer.read().decode("utf-8"))
    except Exception as error:
        sys.stdout.buffer.write(str(error).encode("utf-8", errors="replace"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
