from contextlib import nullcontext

import pytest

from aurora.audio import input as audio


@pytest.mark.parametrize("overflow", [False, True])
def test_capture_blocks(monkeypatch, overflow):
    pcm = bytes(audio.SAMPLES * 4)

    class Input:
        def read(self, count):
            assert count == audio.SAMPLES
            return pcm, overflow

    def open_stream(**options):
        assert options["device"] == 2
        assert options["samplerate"] == 16000
        return nullcontext(Input())

    monkeypatch.setattr(audio.sd, "RawInputStream", open_stream)
    if overflow:
        with pytest.raises(RuntimeError, match="Переполнение"):
            list(audio.capture(2, 2))
    else:
        frames = list(audio.capture(2, 2))
        assert len(frames) == 2
        assert all(f.pcm == pcm and 0 <= f.speech_probability < 0.5 for f in frames)


def test_windows_microphone_list_and_preference(monkeypatch):
    monkeypatch.setattr(audio.sd, "query_hostapis", lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}])
    names = ["Microsoft Sound Mapper - Input", "MCHOSE", "fifine", "fifine", "Output"]
    monkeypatch.setattr(audio.sd, "query_devices", lambda: [
        {"name": name, "hostapi": int(i >= 3), "max_input_channels": int(i != 4)}
        for i, name in enumerate(names)
    ])
    assert audio.microphones() == ["1: MCHOSE (MME)", "2: fifine (MME)"]
    assert audio.select_device(None, "FIFINE") == 2
    assert audio.select_device(1, "fifine") == 1
    with pytest.raises(ValueError):
        audio.select_device(None, "missing")
