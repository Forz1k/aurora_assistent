import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Thread

from PySide6.QtCore import Signal, Slot, Qt, QSettings, QProcess, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QPushButton,
    QMenu, QMessageBox, QTextEdit, QVBoxLayout, QWidget,
)

from aurora.providers.base import LLMProvider, ProviderError
from aurora.providers.ollama_provider import OllamaProvider
from aurora.memory.history import History
from aurora.security.permissions import Decision, Permissions
from aurora.skills.registry import SkillError, default_registry
from aurora.memory.facts import Facts
from aurora.personality.profile import load_prompt
from aurora.tts import design
from aurora.tts.worker import DEFAULT_VOICE, QWEN_ENGINES, VOICES
from aurora.ui import document_dialog
from aurora.ui.provider_dialog import ProviderDialog, openai_provider


class ChatWindow(QWidget):
    finished = Signal(object, str)
    state_changed = Signal(str)

    def __init__(self, history_path=None, base_url="http://127.0.0.1:11434", *,
                 provider: LLMProvider | None = None, microphone=None):

        super().__init__()
        self.resize(680, 500)
        self.system_prompt = load_prompt()
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
        self.microphone = microphone
        self.voice_process = None
        self.speech_process = None
        self.state = "IDLE"
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
        self.memory_button = QPushButton("Память…")
        self.memory_button.clicked.connect(self.edit_facts)
        toolbar.addWidget(self.memory_button)
        self.skills = default_registry(Permissions(self.confirm_skill))
        self.document_pool = ThreadPoolExecutor(max_workers=1)
        self.document_timer = QTimer(self)
        self.document_timer.timeout.connect(self.document_finished)
        self.skill_button = QPushButton("Навыки")
        menu = QMenu(self.skill_button)
        for name, title in self.skills.catalog():
            menu.addAction(title).triggered.connect(lambda checked=False, key=name: self.run_skill(key))
        self.skill_button.setMenu(menu)
        toolbar.addWidget(self.skill_button)
        self.read_aloud = QCheckBox("Озвучивать ответы")
        self.read_aloud.setChecked(self.settings.value("read_aloud", False, type=bool))
        self.read_aloud.toggled.connect(self.toggle_speech)
        layout.addLayout(toolbar)
        speech_options = QHBoxLayout()
        speech_options.addWidget(self.read_aloud)
        self.speaker = QComboBox()
        self.speaker.setAccessibleName("Женский голос")
        for key, label in VOICES.items():
            if key in QWEN_ENGINES and not QWEN_ENGINES[key].installed():
                continue
            self.speaker.addItem(label, key)
        default = self.speaker.itemData(0)
        if default not in QWEN_ENGINES:
            default = self.settings.value("silero_speaker", DEFAULT_VOICE)
        selected = self.settings.value("speech_profile", default)
        self.speaker.setCurrentIndex(max(0, self.speaker.findData(selected)))
        self.speaker.currentIndexChanged.connect(
            lambda: self.settings.setValue("speech_profile", self.speaker.currentData()))
        speech_options.addWidget(self.speaker)
        speech_options.addStretch()
        layout.addLayout(speech_options)
        layout.addWidget(self.transcript)
        layout.addWidget(self.status)
        self.history_status = QLabel(self.history_error)
        self.history_status.setTextFormat(Qt.TextFormat.PlainText)
        self.history_status.setVisible(bool(self.history_error))
        layout.addWidget(self.history_status)
        composer = QHBoxLayout()
        self.voice = QPushButton("Голос")
        self.voice.clicked.connect(self.start_voice)
        composer.addWidget(self.voice)
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
        self.facts = None
        self.messages = []
        self.history_error = ""
        path = self.local_history
        if self.name == "OpenAI":
            path = path.with_name(path.stem + "-openai" + path.suffix)
        try:
            self.history = History(path)
            self.messages = self.history.messages()
            self.facts = Facts(path)
        except (sqlite3.Error, OSError) as error:
            self.history_error = f"История недоступна: {error}"

    def confirm_skill(self, title, arguments, reusable):
        box = QMessageBox(self)
        box.setWindowTitle("Разрешение на действие")
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(f"{title}\nАргументы: {arguments}")
        once = box.addButton("Разрешить один раз", QMessageBox.ButtonRole.AcceptRole)
        session = None
        if reusable:
            session = box.addButton("Разрешить до закрытия чата", QMessageBox.ButtonRole.ActionRole)
        deny = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(deny)
        box.exec()
        if box.clickedButton() is once:
            return Decision.ONCE
        if session is not None and box.clickedButton() is session:
            return Decision.SESSION
        return Decision.DENY

    def run_skill(self, name):
        try:
            if name.startswith("document."):
                args = document_dialog.arguments(self, name)
                if args is None:
                    return
                self.document_job = self.skills.execute(name, args, executor=self.document_pool)
                self.document_title = Path(args["path"]).name
                self.busy = True
                self.status.setText("Обработка документа…")
                self.update_controls()
                self.document_timer.start(100)
            else:
                self.status.setText(self.skills.execute(name, {}))
        except (OSError, SkillError) as error:
            self.status.setText(str(error))

    def document_finished(self):
        if not self.document_job.done():
            return
        self.document_timer.stop()
        self.busy = False
        self.update_controls()
        try:
            result = self.document_job.result()
        except SkillError as error:
            self.status.setText(str(error))
        else:
            self.status.clear()
            document_dialog.show_result(self, self.document_title, result)

    def edit_facts(self):
        try:
            original = self.facts.read()
            edited, accepted = QInputDialog.getMultiLineText(
                self, f"Память · {self.name}",
                f"Эти факты будут отправляться в {self.name} с каждым запросом. "
                "Введите по одному на строку. Чтобы забыть факт, удалите строку.",
                original)
            if accepted:
                self.facts.save(original, edited)
                self.status.setText("Память сохранена.")
        except (sqlite3.Error, ValueError) as error:
            self.status.setText(f"Ошибка памяти: {error}")

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
        self.voice.setEnabled(bool(self.models.count() and not self.busy and not self.input.text()))
        self.stop.setEnabled(any(p is not None for p in (self.reply, self.voice_process, self.speech_process)))
        self.configure.setEnabled(not self.busy)
        self.skill_button.setEnabled(not self.busy)
        self.memory_button.setEnabled(not self.busy and self.facts is not None)
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

    def set_state(self, state, message):
        self.state = state
        self.status.setText(message)
        self.state_changed.emit(state)

    def start_voice(self):
        self.busy = True
        self.input.setReadOnly(True)
        process = QProcess(self)
        self.voice_process = process
        self.voice_text = ""
        self.voice_error = ""
        process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        process.readyReadStandardOutput.connect(self.read_voice)
        process.finished.connect(self.finish_voice)
        process.errorOccurred.connect(self.voice_process_error)
        self.set_state("STARTING", "Подготовка микрофона…")
        self.update_controls()
        process.start(sys.executable, ["-m", "aurora.audio.worker", self.microphone or ""])

    def read_voice(self):
        process = self.voice_process
        labels = {"WAITING": "Скажите «Аврора».", "LISTENING": "Произнесите команду. Запись: 5 с.",
                  "TRANSCRIBING": "Распознаю команду…"}
        while process and process.canReadLine():
            line = bytes(process.readLine())
            if self.state == "CANCELLING":
                continue
            try:
                kind, value = json.loads(line)
                if kind == "state":
                    self.set_state(value, labels[value])
                elif kind == "error":
                    self.voice_error = value
                elif kind == "text":
                    self.voice_text = value.strip()
            except (ValueError, KeyError, TypeError, AttributeError):
                self.voice_error = "Некорректный ответ голосового модуля."

    def voice_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.voice_error = "Не удалось запустить голосовой модуль."
            self.finish_voice(1)

    def finish_voice(self, code, *_):
        if self.voice_process is None:
            return
        cancelled = self.state == "CANCELLING"
        self.read_voice()
        self.voice_process.deleteLater()
        self.voice_process = None
        self.busy = False
        self.input.setReadOnly(False)
        self.update_controls()
        if cancelled:
            self.set_state("CANCELLED", "Голосовой ввод остановлен.")
            return
        if self.voice_error or code or not self.voice_text:
            self.set_state("ERROR", self.voice_error or "Голосовой модуль завершился без команды.")
            return
        self.input.setText(self.voice_text)
        self.submit()

    def submit(self):
        if not self.send.isEnabled():
            return
        self.pending = self.input.text().strip()
        self.input.setReadOnly(True)
        messages = self.messages + [{"role": "user", "content": self.pending}]
        if self.facts is not None:
            try:
                facts = self.facts.read()
                if facts:
                    messages.insert(0, {"role": "user", "content": "Сохранённые сведения пользователя:\n" + facts})
            except sqlite3.Error as error:
                self.history_status.setText(f"Память недоступна: {error}")
                self.history_status.show()
        if self.system_prompt:
            messages.insert(0, {"role": "system", "content": self.system_prompt})
        self.answer = ""
        try:
            self.reply = self.provider.stream(self.models.currentText(), messages)
        except ProviderError as error:
            self.finish_stream(str(error))
            return
        self.reply.chunk.connect(self.receive_text)
        self.reply.finished.connect(self.finish_stream)
        self.busy = True
        self.set_state("THINKING", "Ожидаю ответ…")
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

    def toggle_speech(self, enabled):
        self.settings.setValue("read_aloud", enabled)
        if not enabled and self.speech_process is not None:
            self.cancel()

    def start_speech(self):
        self.busy = True
        process = QProcess(self)
        self.speech_process = process
        process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        process.finished.connect(self.finish_speech)
        process.errorOccurred.connect(self.speech_process_error)
        self.set_state("SPEAKING", "Озвучиваю ответ…")
        self.update_controls()
        speaker = self.speaker.currentData()
        executable = str(design.PYTHON) if speaker in QWEN_ENGINES else sys.executable
        process.start(executable, ["-m", "aurora.tts.worker", "--speaker", speaker])
        process.write(self.answer.encode("utf-8"))
        process.closeWriteChannel()

    def speech_process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.finish_speech(1)

    def finish_speech(self, code, *_):
        process = self.speech_process
        if process is None:
            return
        self.speech_process = None
        self.busy = False
        if self.state == "CANCELLING":
            self.set_state("CANCELLED", "Озвучивание остановлено.")
        elif code:
            reason = bytes(process.readAllStandardOutput()).decode("utf-8", errors="replace")
            self.set_state("ERROR", reason or "Не удалось озвучить ответ.")
        else:
            used_backup = b"AURORA_PIPER_FALLBACK" in bytes(process.readAllStandardOutput()).splitlines()
            self.set_state("IDLE", "Ответ озвучен резервным голосом Piper." if used_backup else "")
        process.deleteLater()
        self.update_controls()

    def cancel(self):
        if self.speech_process is not None:
            self.set_state("CANCELLING", "Остановка озвучивания…")
            self.speech_process.kill()
        if self.voice_process is not None:
            self.set_state("CANCELLING", "Остановка микрофона…")
            self.voice_process.kill()
        if self.reply is not None:
            self.set_state("CANCELLING", "Остановка…")
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
        speak = not error and self.state != "CANCELLING" and self.read_aloud.isChecked()
        if not speak:
            self.set_state("CANCELLED" if self.state == "CANCELLING" else "ERROR" if error else "IDLE", error)
        self.reply = None
        self.pending = ""
        self.busy = False
        self.input.setReadOnly(False)
        self.update_controls()
        self.input.setFocus()

        if speak:
            self.start_speech()

    def closeEvent(self, event):
        self.document_timer.stop()
        self.document_pool.shutdown(wait=False, cancel_futures=True)
        self.cancel()
        if self.voice_process is not None:
            self.voice_process.waitForFinished(1000)
        if self.speech_process is not None:
            self.speech_process.waitForFinished(1000)
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


def run_chat(microphone=None) -> int:
    app = QApplication([])
    window = ChatWindow(microphone=microphone)
    window.show()
    return app.exec()
