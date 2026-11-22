import json
import sqlite3
from pathlib import Path
from threading import Thread

from PySide6.QtCore import Signal, Slot, QUrl, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from aurora.providers import ollama
from aurora.memory.history import History


class ChatWindow(QWidget):
    finished = Signal(object, str)

    def __init__(self, history_path=None, base_url="http://127.0.0.1:11434"):

        super().__init__()
        self.setWindowTitle("Аврора · Чат")
        self.resize(680, 500)
        self.base_url = base_url
        self.network = QNetworkAccessManager(self)
        self.reply = None
        self.history = None
        self.history_error = ""
        self.messages = []
        try:
            self.history = History(history_path or Path(__file__).resolve().parents[2] / "data/chat.sqlite3")
            self.messages = self.history.messages()
        except (sqlite3.Error, OSError) as error:
            self.history = None
            self.history_error = f"История недоступна: {error}"
        self.pending = ""
        self.busy = False
        self.models = QComboBox()
        self.refresh = QPushButton("Обновить")
        self.transcript = QTextEdit(readOnly=True)
        self.input = QLineEdit(placeholderText="Введите сообщение")
        self.send = QPushButton("Отправить")
        self.stop = QPushButton("Остановить")
        self.stop.clicked.connect(self.cancel)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.restore_transcript()
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Модель"))
        toolbar.addWidget(self.models, 1)
        toolbar.addWidget(self.refresh)
        layout.addLayout(toolbar)
        layout.addWidget(self.transcript)
        layout.addWidget(self.status)
        self.history_status = QLabel(self.history_error)
        self.history_status.setTextFormat(Qt.TextFormat.PlainText)
        self.history_status.setVisible(bool(self.history_error))
        layout.addWidget(self.history_status)
        composer = QHBoxLayout()
        composer.addWidget(self.input, 1)
        composer.addWidget(self.send)
        composer.addWidget(self.stop)
        layout.addLayout(composer)
        self.finished.connect(self.complete)
        self.refresh.clicked.connect(self.reload)
        self.send.clicked.connect(self.submit)
        self.input.returnPressed.connect(self.submit)
        self.input.textChanged.connect(self.update_controls)
        self.reload()

    def update_controls(self):
        self.models.setEnabled(not self.busy)
        self.stop.setEnabled(self.reply is not None)
        self.refresh.setEnabled(not self.busy)
        self.send.setEnabled(bool(self.models.count() and self.input.text().strip() and not self.busy))

    def start(self, operation, status):
        self.busy = True
        self.status.setText(status)
        self.update_controls()

        def worker():
            try:
                result = operation()
            except ollama.OllamaError as error:
                self.finished.emit(None, str(error))
            else:
                self.finished.emit(result, "")

        Thread(target=worker, daemon=True).start()

    def reload(self):
        self.start(lambda: ollama.list_models(self.base_url), "Запрашиваю модели…")

    def submit(self):
        if not self.send.isEnabled():
            return
        self.pending = self.input.text().strip()
        self.input.setReadOnly(True)
        messages = self.messages + [{"role": "user", "content": self.pending}]
        payload = {"model": self.models.currentText(), "messages": messages, "stream": True}
        request = QNetworkRequest(QUrl(self.base_url + "/api/chat"))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setTransferTimeout(180000)
        self.reply = self.network.post(request, json.dumps(payload).encode())
        self.reply.readyRead.connect(self.read_chunks)
        self.reply.finished.connect(self.finish_stream)
        self.busy = True
        self.buffer = b""
        self.answer = ""
        self.done = False
        self.failure = ""
        self.status.setText("Ожидаю ответ…")
        self.append_text(f"Вы: {self.pending}\nАврора: ")
        self.update_controls()

    def restore_transcript(self):
        labels = {"user": "Вы", "assistant": "Аврора"}
        self.transcript.setPlainText("\n".join(
            f"{labels[m['role']]}: {m['content']}" for m in self.messages
        ) + ("\n\n" if self.messages else ""))

    def append_text(self, text):
        self.transcript.moveCursor(QTextCursor.MoveOperation.End)
        self.transcript.insertPlainText(text)
        self.transcript.ensureCursorVisible()

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
                    raise ollama.OllamaError("Лишние данные после конца ответа.")
                text, self.done = ollama.decode_chunk(line)
                self.answer += text
                self.append_text(text)
        except ollama.OllamaError as error:
            self.failure = str(error)
            if not final:
                self.reply.abort()

    def cancel(self):
        if self.reply is not None:
            self.failure = "Ответ остановлен."
            self.reply.abort()

    def finish_stream(self):
        reply = self.reply
        if not self.failure:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failure = f"Ошибка Ollama: {reply.errorString()}"
            else:
                self.read_chunks(final=True)
                if not self.failure and not (self.done and self.answer.strip()):
                    self.failure = "Ollama не завершила ответ."
        if self.failure:
            self.restore_transcript()
        else:
            self.messages.extend(({"role": "user", "content": self.pending},
                                  {"role": "assistant", "content": self.answer}))
            self.append_text("\n\n")
            if self.history is not None:
                try:
                    self.history.append(self.pending, self.answer)
                except sqlite3.Error as error:
                    self.history_status.setText(f"Ответ не сохранён: {error}")
                    self.history_status.show()
            self.input.clear()
        self.status.setText(self.failure)
        self.reply = None
        reply.deleteLater()
        self.pending = ""
        self.busy = False
        self.input.setReadOnly(False)
        self.update_controls()
        self.input.setFocus()

    def closeEvent(self, event):
        self.cancel()
        super().closeEvent(event)

    @Slot(object, str)
    def complete(self, result, error):
        self.busy = False
        if error:
            self.status.setText(error)
        else:
            previous = self.models.currentText()
            self.models.clear()
            self.models.addItems(result)
            if previous in result:
                self.models.setCurrentText(previous)
            self.status.setText("" if result else "У Ollama пока нет моделей.")
        self.pending = ""
        self.input.setReadOnly(False)
        self.update_controls()
        self.input.setFocus()


def run_chat() -> int:
    app = QApplication([])
    window = ChatWindow()
    window.show()
    return app.exec()
