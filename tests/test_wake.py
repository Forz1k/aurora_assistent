import json

import pytest

from aurora.audio import wake
from aurora.audio.input import AudioFrame


class Detector:
    def __init__(self, results):
        self.results = iter(results)

    def AcceptWaveform(self, pcm):
        assert pcm == b"\0" * 1024
        return True

    def Result(self):
        return json.dumps({"result": next(self.results)})


FRAME = AudioFrame(bytes(2048), 0)
NAME = {"word": "аврора", "conf": 0.95}
UNKNOWN = {"word": "[unk]", "conf": 1}


@pytest.mark.parametrize("words", [[], [UNKNOWN], [UNKNOWN, NAME], [dict(NAME, conf=0.4)]])
def test_reject_unrelated_or_uncertain(words):
    assert not wake.wait_for_name([FRAME], Detector([words]))


def test_wait_continues_on_same_microphone(monkeypatch, capsys):
    opens = []

    def capture(device, length):
        opens.append(device)
        yield from [FRAME, FRAME, FRAME]

    monkeypatch.setattr(wake, "capture", capture)
    monkeypatch.setattr(wake, "make_detector", lambda: Detector([[], [UNKNOWN], [NAME]]))
    monkeypatch.setattr(wake, "recognize_command", lambda device, seconds: (device, seconds))
    assert wake.listen(2, 5) == (2, 5)
    assert opens == [2]
    assert capsys.readouterr().out.count("Ctrl+C") == 1
