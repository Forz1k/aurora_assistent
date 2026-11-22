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
