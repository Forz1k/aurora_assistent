from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
)

from aurora.providers.base import ProviderError
from aurora.providers.openai_provider import OpenAIProvider
from aurora.security import credentials


def openai_provider(model, new_key=""):
    key = new_key.strip() or credentials.read_key()
    provider = OpenAIProvider(key, model)
    if new_key.strip():
        credentials.write_key(key)
    return provider


class ProviderDialog(QDialog):
    def __init__(self, name, model, parent):
        super().__init__(parent)
        self.setWindowTitle("Настройки провайдера")
        self.name = QComboBox()
        self.name.addItems(["Ollama", "OpenAI"])
        self.name.setCurrentText(name)
        self.model = QLineEdit(model)
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Оставьте пустым для сохранённого ключа")
        self.error = QLabel()
        self.provider = None
        layout = QFormLayout(self)
        layout.addRow("Провайдер", self.name)
        layout.addRow("Модель OpenAI", self.model)
        layout.addRow("API-ключ", self.key)
        layout.addRow(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.name.currentTextChanged.connect(self.update_fields)
        self.update_fields(name)

    def update_fields(self, name):
        self.model.setEnabled(name == "OpenAI")
        self.key.setEnabled(name == "OpenAI")

    def accept(self):
        if self.name.currentText() == "OpenAI":
            try:
                self.provider = openai_provider(self.model.text().strip(), self.key.text())
            except ProviderError as error:
                self.error.setText(str(error))
                return
        self.key.clear()
        super().accept()
