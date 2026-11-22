import json

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from aurora.providers.base import ChatStream, ProviderError


class OpenAIProvider:
    """Клиент Responses API с явно выбранной текстовой моделью."""

    def __init__(self, api_key: str, model: str):
        if not api_key.strip() or not model.strip():
            raise ProviderError("Для OpenAI укажите API-ключ и текстовую модель.")
        self._key = api_key.strip()
        self.model = model.strip()
        self.network = None

    def list_models(self) -> list[str]:
        return [self.model]

    def stream(self, model: str, messages: list[dict[str, str]]) -> ChatStream:
        if model != self.model:
            raise ProviderError("Выбранная модель OpenAI не настроена.")
        request = QNetworkRequest(QUrl("https://api.openai.com/v1/responses"))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"Authorization", b"Bearer " + self._key.encode())
        request.setTransferTimeout(180000)
        if self.network is None:
            self.network = QNetworkAccessManager()
        payload = {"model": model, "input": messages, "stream": True, "store": False}
        reply = self.network.post(request, json.dumps(payload).encode())
        return ResponsesStream(reply)


class ResponsesStream(ChatStream):
    def __init__(self, reply):
        super().__init__(reply)
        self.reply = reply
        self.buffer = b""
        self.data = []
        self.completed = False
        self.has_text = False
        self.failure = ""
        reply.readyRead.connect(self.read_events)
        reply.finished.connect(self.finish)

    def consume_line(self, line):
        if line.startswith(b"data:"):
            self.data.append(line[5:].lstrip(b" "))
        elif not line and self.data:
            event = json.loads(b"\n".join(self.data))
            self.data.clear()
            if not isinstance(event, dict):
                raise ValueError
            kind = event.get("type")
            if kind in ("response.output_text.delta", "response.refusal.delta"):
                delta = event.get("delta")
                if not isinstance(delta, str) or self.completed:
                    raise ValueError
                self.has_text |= bool(delta.strip())
                self.chunk.emit(delta)
            elif kind == "response.completed":
                self.completed = True
            elif kind in ("error", "response.failed", "response.incomplete"):
                raise ProviderError(f"OpenAI не завершил генерацию ({kind}).")

    def read_events(self, final=False):
        status = self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status != 200:
            self.reply.readAll()
            return
        lines = (self.buffer + bytes(self.reply.readAll())).split(b"\n")
        self.buffer = lines.pop()
        if final:
            lines.extend([self.buffer, b""])
        try:
            for line in lines:
                self.consume_line(line.rstrip(b"\r"))
        except (ValueError, ProviderError) as error:
            self.failure = str(error) if isinstance(error, ProviderError) else "Некорректный поток OpenAI."
            if not final:
                self.reply.abort()

    def cancel(self):
        self.failure = "Ответ остановлен."
        self.reply.abort()

    def finish(self):
        if not self.failure:
            status = self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if self.reply.error() != QNetworkReply.NetworkError.NoError or status != 200:
                self.failure = f"Ошибка OpenAI (HTTP {status})." if status else "Нет связи с OpenAI."
            else:
                self.read_events(final=True)
                if not self.failure and not (self.completed and self.has_text):
                    self.failure = "Неполный ответ OpenAI."
        self.finished.emit(self.failure)
        self.reply.deleteLater()
