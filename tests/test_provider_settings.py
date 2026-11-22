import os
from uuid import uuid4

import win32cred
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from aurora.providers.ollama_provider import OllamaProvider
from aurora.security import credentials
from aurora.ui.chat import ChatWindow


def test_switch_restore_and_replace_key(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    target = f"Aurora-test/{uuid4()}"
    monkeypatch.setattr(credentials, "TARGET", target)
    monkeypatch.setattr(OllamaProvider, "list_models", lambda self: ["local"])
    path = tmp_path / "chat.sqlite3"
    window = ChatWindow(path)

    def ready():
        for _ in range(500):
            if not window.busy:
                return
            QTest.qWait(10)
        raise AssertionError("Окно занято")

    def choose(name, key=""):
        def apply():
            dialog = app.activeModalWidget()
            dialog.name.setCurrentText(name)
            dialog.model.setText("test-model")
            dialog.key.setText(key)
            dialog.accept()
            if dialog.isVisible():
                dialog.reject()
        QTimer.singleShot(0, apply)
        window.configure.click()
        ready()

    try:
        ready()
        window.history.append("local question", "local answer")
        choose("OpenAI", "sample-key-1")
        assert credentials.read_key() == "sample-key-1"
        assert not window.messages
        window.history.append("cloud question", "cloud answer")
        choose("OpenAI", "sample-key-2")
        assert credentials.read_key() == "sample-key-2"
        window.close()
        window = ChatWindow(path)
        ready()
        assert window.name == "OpenAI" and window.models.currentText() == "test-model"
        assert window.messages[0]["content"] == "cloud question"
        assert b"sample-key" not in path.with_suffix(".ini").read_bytes()
        choose("Ollama")
        assert window.messages[0]["content"] == "local question"
    finally:
        window.close()
        if credentials.read_key():
            win32cred.CredDelete(target, win32cred.CRED_TYPE_GENERIC)
