"""Редактор и последовательное выполнение явно выбранных пользователем навыков."""

import json
import logging
from time import monotonic

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QListWidget, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from aurora.skills.registry import SkillError
from aurora.ui import document_dialog


class ChainDialog(QDialog):
    def __init__(self, registry, executor, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.executor = executor
        self.steps = []
        self.index = 0
        self.running = False
        self.stop_reason = ""
        self.job = None
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.advance)

        self.setWindowTitle("Цепочка действий")
        self.resize(650, 480)
        layout = QVBoxLayout(self)
        tools = QHBoxLayout()
        self.choice = QComboBox()
        for name, title in registry.catalog():
            self.choice.addItem(title, name)
        tools.addWidget(self.choice, 1)
        self.add_button = QPushButton("Добавить шаг")
        self.add_button.clicked.connect(self.add_step)
        tools.addWidget(self.add_button)
        self.remove_button = QPushButton("Убрать шаг")
        self.remove_button.clicked.connect(self.remove_step)
        tools.addWidget(self.remove_button)
        layout.addLayout(tools)
        self.plan = QListWidget()
        self.plan.currentRowChanged.connect(self.update_buttons)
        layout.addWidget(self.plan)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.results = QPlainTextEdit(readOnly=True)
        layout.addWidget(self.results)
        controls = QHBoxLayout()
        self.start_button = QPushButton("Выполнить по порядку")
        self.start_button.clicked.connect(self.start)
        controls.addWidget(self.start_button)
        self.stop_button = QPushButton("Остановить")
        self.stop_button.clicked.connect(self.stop)
        controls.addWidget(self.stop_button)
        layout.addLayout(controls)
        self.update_buttons()

    def update_buttons(self):
        self.choice.setEnabled(not self.running)
        self.add_button.setEnabled(not self.running)
        self.remove_button.setEnabled(not self.running and self.plan.currentRow() >= 0)
        self.start_button.setEnabled(bool(self.steps) and not self.running)
        self.stop_button.setEnabled(self.running and not self.stop_reason)

    def add_step(self):
        name, title = self.choice.currentData(), self.choice.currentText()
        try:
            args = document_dialog.arguments(self, name) if name.startswith("document.") else {}
        except OSError as error:
            self.status.setText(str(error))
            return
        if args is None:
            return
        self.steps.append((name, title, args))
        details = json.dumps(args, ensure_ascii=False) if args else ""
        self.plan.addItem(f"{title} {details}".strip())
        self.plan.setCurrentRow(len(self.steps) - 1)
        self.update_buttons()

    def remove_step(self):
        row = self.plan.currentRow()
        if row >= 0:
            del self.steps[row]
            self.plan.takeItem(row)
        self.update_buttons()

    def start(self):
        if self.running or not self.steps:
            return
        self.running = True
        self.index = 0
        self.job = None
        self.stop_reason = ""
        self.results.clear()
        self.update_buttons()
        self.timer.start()

    def stop(self):
        self.stop_reason = "Остановлено пользователем."
        if self.job is not None and self.job.cancel():
            self.job = None
        self.status.setText("Остановка после текущего действия…")
        self.update_buttons()

    def finish(self, reason):
        self.timer.stop()
        self.running = False
        self.status.setText(f"{reason} Выполнено шагов: {self.index} из {len(self.steps)}.")
        logging.info("Цепочка завершена: %d/%d", self.index, len(self.steps))
        self.update_buttons()

    def advance(self):
        if self.job is not None:
            if not self.job.done():
                if not self.stop_reason and monotonic() >= self.deadline:
                    self.stop()
                    self.stop_reason = "Истекло время ожидания шага."
                    self.status.setText(self.stop_reason + " Ожидаю завершения текущего действия.")
                return
            try:
                result = self.job.result()
            except SkillError as error:
                self.job = None
                self.finish(str(error))
                return
            self.job = None
            self.index += 1
            self.results.appendPlainText(f"{self.index}. {self.steps[self.index-1][1]}\n{result}\n")
        if self.stop_reason or self.index == len(self.steps):
            self.finish(self.stop_reason or "Готово.")
            return
        name, title, args = self.steps[self.index]
        self.status.setText(f"Шаг {self.index+1} из {len(self.steps)}: {title}")
        # Диалог разрешений запускает вложенный цикл Qt.
        self.timer.stop()
        try:
            self.job = self.registry.execute(name, args, executor=self.executor)
        except SkillError as error:
            self.finish(str(error))
            return
        self.deadline = monotonic() + 30
        self.timer.start()

    def reject(self):
        if self.running:
            self.stop()
        else:
            super().reject()

    def closeEvent(self, event):
        if self.running:
            self.stop()
            event.ignore()
        else:
            super().closeEvent(event)
