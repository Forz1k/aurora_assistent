import os
import sys

import pytest
from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QApplication

from aurora.providers.base import ChatStream
from aurora.ui import chat
from test_chat_stream import wait_until


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
def test_voice_to_provider(tmp_path, monkeypatch, outcome):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    calls = []

    class Provider:
        def list_models(self):
            return ["model"]

        def stream(self, model, messages):
            calls.append((model, messages))
            reply = ChatStream()
            QTimer.singleShot(0, lambda: (reply.chunk.emit("OK"), reply.finished.emit("")))
            return reply

    class VoiceProcess(QProcess):
        def start(self, executable, args):
            assert args == ["-m", "aurora.audio.worker", "fifine"]
            events = ['print(\'["state","WAITING"]\', flush=True)']
            if outcome == "success":
                for kind, value in [("state", "LISTENING"), ("state", "TRANSCRIBING"), ("text", "hello")]:
                    events.append(f'print(\'["{kind}","{value}"]\', flush=True)')
            elif outcome == "error":
                events.append('print(\'["error","no speech"]\', flush=True)')
            else:
                events.append("import time; time.sleep(30)")
            super().start(sys.executable, ["-c", "\n".join(events)])

    monkeypatch.setattr(chat, "QProcess", VoiceProcess)
    w = chat.ChatWindow(tmp_path / "chat.db", microphone="fifine", provider=Provider())
    states = []
    w.state_changed.connect(states.append)
    try:
        wait_until(lambda: not w.busy)
        w.voice.click()
        if outcome == "cancel":
            wait_until(lambda: w.state == "WAITING")
            w.stop.click()
        wait_until(lambda: not w.busy)
        if outcome == "success":
            assert states == ["STARTING", "WAITING", "LISTENING", "TRANSCRIBING", "THINKING", "IDLE"]
            assert calls == [("model", [{"role": "user", "content": "hello"}])]
            assert w.history.messages()[-1]["content"] == "OK"
        else:
            assert w.state == ("ERROR" if outcome == "error" else "CANCELLED")
            assert not calls and not w.history.messages()
        assert w.voice.isEnabled()
    finally:
        w.close()
        app.processEvents()
