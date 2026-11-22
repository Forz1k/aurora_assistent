import csv
import wave
from types import SimpleNamespace

import pytest

from aurora.tts import studio


def test_prepare_preserves_source_samples_and_review(tmp_path, monkeypatch):
    source = tmp_path / "sample.wav"
    pcm = bytes(range(256)) * 750
    with wave.open(str(source), "wb") as out:
        out.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
        out.writeframes(pcm)
    monkeypatch.setattr(studio, "get_speech_timestamps", lambda *_: [{"start": 1600, "end": 6400}])
    segment = SimpleNamespace(text="<test>")
    model = SimpleNamespace(transcribe=lambda *a, **kw: ([segment], None))
    monkeypatch.setattr(studio, "load_model", lambda: model)
    project = tmp_path / "review"
    studio.prepare(source, project)
    with (project / "manifest.csv").open(encoding="utf-8-sig", newline="") as manifest:
        rows = list(csv.reader(manifest, delimiter=";"))
    assert rows[1][1:4] == ["0.1", "0.4", "<test>"]
    with wave.open(str(project / rows[1][0])) as clip:
        assert clip.getnchannels() == 2
        assert clip.readframes(clip.getnframes()) == pcm[4800 * 4:19200 * 4]
    assert "&lt;test&gt;" in (project / "review.html").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        studio.prepare(source, project)
