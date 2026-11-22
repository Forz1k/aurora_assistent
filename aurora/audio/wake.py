"""Ожидание отдельного обращения по имени, затем запись одной команды."""

import re
from collections import deque
from contextlib import closing

from aurora.audio.input import capture
from aurora.audio.stt import recognize_command, transcribe


def next_utterance(frames) -> bytes:
    # 256 мс до начала речи и 480 мс тишины после неё.
    lead = deque(maxlen=8)
    parts = []
    quiet = 0
    for frame in frames:
        speech = frame.speech_probability >= 0.5
        if not parts:
            lead.append(frame.pcm)
            if speech:
                parts.extend(lead)
                lead.clear()
        else:
            parts.append(frame.pcm)
            quiet = 0 if speech else quiet + 1
            if quiet >= 15 or len(parts) >= 125:
                break
    return b"".join(parts)


def listen(device: int | None, seconds: int) -> str:
    while True:
        print("Ожидаю имя «Аврора». Для выхода нажмите Ctrl+C.", flush=True)
        with closing(capture(device, None)) as frames:
            pcm = next_utterance(frames)
        try:
            name = transcribe(pcm)
        except Exception as error:
            raise RuntimeError(f"Не удалось распознать обращение: {error}") from error
        if re.findall(r"\w+", name.casefold()) == ["аврора"]:
            return recognize_command(device, seconds)
