import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import monotonic

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from aurora.ui.chat import ChatWindow


def wait_until(condition):
    deadline = monotonic() + 5
    while not condition():
        assert monotonic() < deadline
        QTest.qWait(10)


def test_stream_cancel_retry_and_reopen(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    release = Event()
    requests = []

    class Server(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"models":[{"name":"test"}]}')

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(payload)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"message":{"content":"one"},"done":false}\n')
            self.wfile.flush()
            if len(requests) == 1:
                release.wait(5)
                return
            if len(requests) == 2:
                return
            self.wfile.write(b'{"message":{"content":" two"},"done":true}')

    with ThreadingHTTPServer(("127.0.0.1", 0), Server) as server:
        Thread(target=server.serve_forever, daemon=True).start()
        args = (tmp_path / "history.db", f"http://127.0.0.1:{server.server_port}")
        window = ChatWindow(*args)
        try:
            wait_until(lambda: not window.busy)
            window.input.setText("Hello")
            window.send.click()
            wait_until(lambda: "one" in window.transcript.toPlainText())
            window.stop.click()
            wait_until(lambda: not window.busy)
            assert window.input.text() == "Hello"
            assert not window.history.messages()
            release.set()
            window.send.click()
            wait_until(lambda: not window.busy)
            assert window.status.text() and not window.messages
            window.send.click()
            wait_until(lambda: not window.busy)
            assert window.messages[-1]["content"] == "one two"
            window.close()
            reopened = ChatWindow(*args)
            wait_until(lambda: not reopened.busy)
            assert reopened.messages == window.messages
            reopened.input.setText("Again")
            reopened.send.click()
            wait_until(lambda: not reopened.busy)
            assert requests[-1]["messages"][:-1] == window.messages
            assert requests[-1]["stream"] is True
            reopened.close()
        finally:
            release.set()
            window.close()
            server.shutdown()
            app.processEvents()


def test_injected_provider(tmp_path):
    from PySide6.QtCore import QTimer
    from aurora.providers.base import ChatStream

    class StubProvider:
        def list_models(self):
            return ["stub"]

        def stream(self, model, messages):
            assert model == "stub"
            assert messages == [{"role": "user", "content": "Hello"}]
            stream = ChatStream()
            def respond():
                stream.chunk.emit("OK")
                stream.finished.emit("")
            QTimer.singleShot(0, respond)
            return stream

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    window = ChatWindow(tmp_path / "history.db", provider=StubProvider())
    try:
        wait_until(lambda: not window.busy)
        window.input.setText("Hello")
        window.send.click()
        wait_until(lambda: not window.busy)
        assert window.history.messages()[-1]["content"] == "OK"
    finally:
        window.close()
        app.processEvents()
