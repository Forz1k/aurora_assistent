import sqlite3
from pathlib import Path
from threading import Thread

from PySide6.QtCore import Signal, Slot, Qt, QSettings
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from aurora.providers.base import LLMProvider, ProviderError
from aurora.providers.ollama_provider import OllamaProvider
from aurora.memory.history import History
from aurora.ui.provider_dialog import ProviderDialog, openai_provider


class ChatWindow(QWidget):
    finished = Signal(object, str)

    def __init__(self, history_path=None, base_url="http://127.0.0.1:11434", *,
                 provider: LLMProvider | None = None):

        super().__init__()
        self.resize(680, 500)
        self.local_history = Path(history_path or Path(__file__).resolve().parents[2] / "data/chat.sqlite3")
        self.settings = QSettings(str(self.local_history.with_suffix(".ini")), QSettings.Format.IniFormat)
        self.local_provider = provider if provider is not None else OllamaProvider(base_url)
        self.provider = self.local_provider
        self.name = "Ollama"
        self.model = str(self.settings.value("openai_model", ""))
        startup_error = ""
        if provider is None and self.settings.value("provider") == "OpenAI":
            self.name = "OpenAI"
            try:
                self.provider = openai_provider(self.model)
            except ProviderError as error:
                self.provider = None
                startup_error = str(error)
        self.setWindowTitle(f"Аврора · {self.name}")
        self.reply = None
        self.load_history()
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
        self.configure = QPushButton("Провайдер…")
        self.configure.clicked.connect(self.configure_provider)
        toolbar.addWidget(self.configure)
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
        if startup_error:
            self.status.setText(startup_error)
            self.update_controls()
        else:
            self.reload()

    def load_history(self):
        self.history = None
        self.messages = []
        self.history_error = ""
        path = self.local_history
        if self.name == "OpenAI":
            path = path.with_name(path.stem + "-openai" + path.suffix)
        try:
            self.history = History(path)
            self.messages = self.history.messages()
        except (sqlite3.Error, OSError) as error:
            self.history_error = f"История недоступна: {error}"

    def configure_provider(self):
        dialog = ProviderDialog(self.name, self.model, self)
        try:
            if not dialog.exec():
                return
            previous = self.name
            self.name = dialog.name.currentText()
            self.provider = dialog.provider if self.name == "OpenAI" else self.local_provider
            self.model = dialog.model.text().strip()
        finally:
            dialog.deleteLater()
        self.settings.setValue("provider", self.name)
        self.settings.setValue("openai_model", self.model)
        self.settings.sync()
        self.setWindowTitle(f"Аврора · {self.name}")
        if previous != self.name:
            self.input.clear()
            self.load_history()
            self.restore_transcript()
        warning = self.history_error
        if self.settings.status() != QSettings.Status.NoError:
            warning += " Не удалось сохранить выбор провайдера."
        self.history_status.setText(warning)
        self.history_status.setVisible(bool(warning))
        self.models.clear()
        self.reload()

    def update_controls(self):
        self.models.setEnabled(not self.busy)
        self.stop.setEnabled(self.reply is not None)
        self.configure.setEnabled(not self.busy)
        self.refresh.setEnabled(not self.busy and self.provider is not None)
        self.send.setEnabled(bool(self.models.count() and self.input.text().strip() and not self.busy))

    def start(self, operation, status):
        self.busy = True
        self.status.setText(status)
        self.update_controls()

        def worker():
            try:
                result = operation()
            except ProviderError as error:
                self.finished.emit(None, str(error))
            else:
                self.finished.emit(result, "")

        Thread(target=worker, daemon=True).start()

    def reload(self):
        self.start(self.provider.list_models, "Запрашиваю модели…")

    def submit(self):
        if not self.send.isEnabled():
            return
        self.pending = self.input.text().strip()
        self.input.setReadOnly(True)
        messages = self.messages + [{"role": "user", "content": self.pending}]
        self.answer = ""
        try:
            self.reply = self.provider.stream(self.models.currentText(), messages)
        except ProviderError as error:
            self.finish_stream(str(error))
            return
        self.reply.chunk.connect(self.receive_text)
        self.reply.finished.connect(self.finish_stream)
        self.busy = True
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

    def receive_text(self, text):
        self.answer += text
        self.append_text(text)

    def cancel(self):
        if self.reply is not None:
            self.reply.cancel()

    def finish_stream(self, error):
        if error:
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
        self.status.setText(error)
        self.reply = None
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
            self.status.setText("" if result else "Список моделей пуст.")
        self.pending = ""
        self.input.setReadOnly(False)
        self.update_controls()
        self.input.setFocus()


def run_chat() -> int:
    app = QApplication([])
    window = ChatWindow()
    window.show()
    return app.exec()
