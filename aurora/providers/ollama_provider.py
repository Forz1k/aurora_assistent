import json

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from aurora.providers.base import ChatStream
from aurora.providers.ollama import OllamaError, decode_chunk, list_models


class OllamaProvider:
    def __init__(self, base_url="http://127.0.0.1:11434"):
        self.base_url = base_url.rstrip("/")
        self.network = None

    def list_models(self) -> list[str]:
        return list_models(self.base_url)

    def stream(self, model: str, messages: list[dict[str, str]]) -> ChatStream:
        payload = {"model": model, "messages": messages, "stream": True}
        request = QNetworkRequest(QUrl(self.base_url + "/api/chat"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(180000)
        if self.network is None:
            self.network = QNetworkAccessManager()
        reply = self.network.post(request, json.dumps(payload).encode())
        return OllamaStream(reply)


class OllamaStream(ChatStream):
    def __init__(self, reply):
        super().__init__(reply)
        self.reply = reply
        self.buffer = b""
        self.done = False
        self.has_text = False
        self.failure = ""
        reply.readyRead.connect(self.read_chunks)
        reply.finished.connect(self.finish)

    def read_chunks(self, final=False):
        self.buffer += bytes(self.reply.readAll())
        lines = self.buffer.split(b"\n")
        self.buffer = lines.pop()
        if final and self.buffer:
            lines.append(self.buffer)
            self.buffer = b""
        try:
            for line in lines:
                if not line.strip():
                    continue
                if self.done:
                    raise OllamaError("Лишние данные после конца ответа.")
                text, self.done = decode_chunk(line)
                if text:
                    self.has_text |= bool(text.strip())
                    self.chunk.emit(text)
        except OllamaError as error:
            self.failure = str(error)
            if not final:
                self.reply.abort()

    def cancel(self):
        self.failure = "Ответ остановлен."
        self.reply.abort()

    def finish(self):
        if not self.failure:
            if self.reply.error() != QNetworkReply.NetworkError.NoError:
                self.failure = f"Ошибка Ollama: {self.reply.errorString()}"
            else:
                self.read_chunks(final=True)
                if not self.failure and not (self.done and self.has_text):
                    self.failure = "Ollama не завершила ответ."
        self.finished.emit(self.failure)
        self.reply.deleteLater()
