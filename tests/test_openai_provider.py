import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread
from time import monotonic

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from aurora.providers.openai_provider import OpenAIProvider


@pytest.mark.parametrize("case", ["success", "cancel", "401", "truncated", "failed"])
def test_responses_stream(case):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    release = Event()
    observed = {}

    class Server(BaseHTTPRequestHandler):
        def do_POST(self):
            observed["auth"] = self.headers["Authorization"]
            observed["payload"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(401 if case == "401" else 200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            if case == "401":
                return
            self.wfile.write(b'data: {"type":"response.output_text.delta","delta":"Hi"}\r\n\r\n')
            self.wfile.flush()
            if case == "cancel":
                release.wait(5)
            elif case == "success":
                self.wfile.write(b'data: {"type":"response.completed"}\n\n')
            elif case == "failed":
                self.wfile.write(b'data: {"type":"response.failed"}\n\n')

    with ThreadingHTTPServer(("127.0.0.1", 0), Server) as server:
        class LocalNetwork(QNetworkAccessManager):
            def post(self, request, body):
                assert request.url().toString() == "https://api.openai.com/v1/responses"
                local = QNetworkRequest(request)
                local.setUrl(QUrl(f"http://127.0.0.1:{server.server_port}/"))
                return super().post(local, body)

        Thread(target=server.serve_forever, daemon=True).start()
        try:
            provider = OpenAIProvider("test-key", "test-model")
            provider.network = LocalNetwork()
            messages = [{"role": "user", "content": "Hello"}]
            stream = provider.stream(provider.list_models()[0], messages)
            chunks, ends = [], []
            stream.chunk.connect(chunks.append)
            stream.finished.connect(ends.append)
            deadline = monotonic() + 5
            while not ends:
                assert monotonic() < deadline
                QTest.qWait(10)
                if case == "cancel" and chunks and not ends:
                    stream.cancel()
            assert observed["auth"] == "Bearer test-key"
            assert observed["payload"] == dict(model="test-model", input=messages, stream=True, store=False)
            assert chunks == ([] if case == "401" else ["Hi"])
            assert len(ends) == 1
            assert bool(ends[0]) == (case != "success")
            if case == "401":
                assert "401" in ends[0]
        finally:
            release.set()
            server.shutdown()
            app.processEvents()
