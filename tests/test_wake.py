from aurora.audio import wake
from aurora.audio.input import AudioFrame


def test_wake_requires_standalone_name(monkeypatch):
    heard = iter(["Проект Аврора.", "АВРОРА!"])
    def speech(device, frames):
        assert device == 2 and frames is None
        yield AudioFrame(b"x", 1)

    monkeypatch.setattr(wake, "capture", speech)
    monkeypatch.setattr(wake, "transcribe", lambda pcm: next(heard))
    monkeypatch.setattr(wake, "recognize_command", lambda device, seconds: (device, seconds))
    assert wake.listen(2, 3) == (2, 3)


def test_utterance_stops_after_pause():
    quiet = AudioFrame(b"q", 0.0)
    speech = AudioFrame(b"s", 1.0)
    frames = iter([quiet] * 12 + [speech] * 2 + [quiet] * 15 + [speech])
    assert wake.next_utterance(frames) == b"q" * 7 + b"ss" + b"q" * 15
    assert next(frames) == speech
