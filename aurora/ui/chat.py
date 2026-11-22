from functools import partial
from threading import Thread

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from aurora.providers import ollama


class ChatWindow(QWidget):
    finished = Signal(object, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Аврора · Чат")
        self.resize(680, 500)
        self.messages = []
        self.pending = ""
        self.busy = False
        self.models = QComboBox()
        self.refresh = QPushButton("Обновить")
        self.transcript = QTextEdit(readOnly=True)
        self.input = QLineEdit(placeholderText="Введите сообщение")
        self.send = QPushButton("Отправить")
        self.status = QLabel()
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Модель"))
        toolbar.addWidget(self.models, 1)
        toolbar.addWidget(self.refresh)
        layout.addLayout(toolbar)
        layout.addWidget(self.transcript)
        layout.addWidget(self.status)
        composer = QHBoxLayout()
        composer.addWidget(self.input, 1)
        composer.addWidget(self.send)
        layout.addLayout(composer)
        self.finished.connect(self.complete)
        self.refresh.clicked.connect(self.reload)
        self.send.clicked.connect(self.submit)
        self.input.returnPressed.connect(self.submit)
        self.input.textChanged.connect(self.update_controls)
        self.reload()

    def update_controls(self):
        self.models.setEnabled(not self.busy)
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
        self.start(ollama.list_models, "Запрашиваю модели…")

    def submit(self):
        if not self.send.isEnabled():
            return
        self.pending = self.input.text().strip()
        self.input.setReadOnly(True)
        messages = self.messages + [{"role": "user", "content": self.pending}]
        self.start(partial(ollama.chat, self.models.currentText(), messages), "Ожидаю ответ…")

    @Slot(object, str)
    def complete(self, result, error):
        self.busy = False
        if error:
            self.status.setText(error)
        elif self.pending:
            for role, content in (("user", self.pending), ("assistant", result)):
                self.messages.append({"role": role, "content": content})
            self.transcript.setPlainText(self.transcript.toPlainText() +
                                         f"Вы: {self.pending}\nАврора: {result}\n\n")
            self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())
            self.input.clear()
            self.status.clear()
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
