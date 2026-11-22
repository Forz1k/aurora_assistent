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

    class SpeechProcess(QProcess):
        def start(self, executable, args):
            assert args == ["-m", "aurora.tts.worker"]
            script = "import sys,time; assert sys.stdin.buffer.read().decode() == 'Ответ'; "
            script += {"success": "sys.exit(0)", "error": "sys.exit(1)", "cancel": "time.sleep(30)"}[outcome]
            super().start(sys.executable, ["-c", script])

    monkeypatch.setattr(chat, "QProcess", SpeechProcess)
    window = chat.ChatWindow(tmp_path / "chat.db", provider=Provider())
    try:
        wait_until(lambda: not window.busy)
        window.read_aloud.setChecked(True)
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
