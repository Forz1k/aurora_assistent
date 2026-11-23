"""Выбор документа и ввод параметров для меню навыков."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QPlainTextEdit, QVBoxLayout,
)


def arguments(parent, name):
    editing = name == "document.append"
    formats = "*.txt *.docx" if editing else "*.txt *.docx *.pdf *.xlsx"
    path, _ = QFileDialog.getOpenFileName(parent, "Выберите документ", "", f"Документы ({formats})")
    if not path:
        return None
    args = {"path": path}
    if editing:
        stat = Path(path).stat()
        text, ok = QInputDialog.getMultiLineText(parent, "Добавление текста", "Текст в конце документа")
        if not ok or not text.strip():
            return None
        args.update(text=text, modified_ns=stat.st_mtime_ns, size=stat.st_size)
    elif name == "document.search":
        query, ok = QInputDialog.getText(parent, "Поиск в документе", "Найти текст")
        if not ok or not query.strip():
            return None
        args["query"] = query
    return args


def show_result(parent, title, text):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(720, 460)
    layout = QVBoxLayout(dialog)
    viewer = QPlainTextEdit(readOnly=True)
    viewer.setPlainText(text)
    layout.addWidget(viewer)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
    dialog.deleteLater()
