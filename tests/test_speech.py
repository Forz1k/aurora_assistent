import os
import sys

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication

from aurora.ui import chat
from test_chat_stream import wait_until


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
def test_speech_preserves_completed_turn(tmp_path, monkeypatch, outcome):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])

    class Provider:
        def list_models(self):
            return ["test"]

    monkeypatch.setattr(chat.design, "installed", lambda: True)
    speaker = chat.design.SPEAKER if outcome == "success" else "baya"

    class SpeechProcess(QProcess):
        def start(self, executable, args):
            assert args == ["-m", "aurora.tts.worker", "--speaker", speaker]
            assert executable == (str(chat.design.PYTHON) if speaker == chat.design.SPEAKER else sys.executable)
            script = "import sys,time; assert sys.stdin.buffer.read().decode() == 'Ответ'; "
            script += {"success": "sys.exit(0)", "error": "sys.exit(1)", "cancel": "time.sleep(30)"}[outcome]
            super().start(sys.executable, ["-c", script])

    monkeypatch.setattr(chat, "QProcess", SpeechProcess)
    window = chat.ChatWindow(tmp_path / "chat.db", provider=Provider())
    try:
        wait_until(lambda: not window.busy)
        window.read_aloud.setChecked(True)
        assert window.speaker.currentData() == chat.design.SPEAKER
        window.speaker.setCurrentIndex(window.speaker.findData(speaker))
        window.pending, window.answer = "Вопрос", "Ответ"
        window.finish_stream("")
        assert window.state == "SPEAKING"
        if outcome == "cancel":
            window.stop.click()
        wait_until(lambda: not window.busy)
        assert window.state == {"success": "IDLE", "error": "ERROR", "cancel": "CANCELLED"}[outcome]
        assert window.history.messages()[-1]["content"] == "Ответ"
    finally:
        window.close()
        app.processEvents()


def test_cached_speech_is_persistent_and_voice_specific(tmp_path, monkeypatch):
    from aurora.tts import worker
    from aurora.tts.cache import AudioCache

    calls = []
    monkeypatch.setattr(worker, "load_voice", lambda: calls.append(1))
    monkeypatch.setattr(worker, "synthesize", lambda model, text, speaker: [speaker.encode()])
    for speaker in ("xenia", "xenia", "baya"):
        cache = AudioCache(tmp_path / "speech.db")
        try:
            assert list(worker.render("Привет!", speaker, cache)) == [(48000, speaker.encode())]
        finally:
            cache.db.close()
    assert len(calls) == 2


def test_designed_voice_cache_skips_model_load(tmp_path, monkeypatch):
    from aurora.tts import design, worker
    from aurora.tts.cache import AudioCache

    loads = []
    monkeypatch.setattr(design, "load_model", lambda: loads.append(1) or object())
    monkeypatch.setattr(design, "synthesize", lambda model, text: b"voice")
    cache = AudioCache(tmp_path / "speech.db")
    try:
        for _ in range(2):
            assert list(worker.render("Привет!", design.SPEAKER, cache)) == [(24000, b"voice")]
        assert loads == [1]
        assert cache.get("silero-v5_6_ru:xenia:48000", "Привет!") is None
    finally:
        cache.db.close()
