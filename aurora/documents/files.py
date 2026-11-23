"""Работа с выбранным документом. Результаты содержат обычный текст."""

import codecs
import os
import tempfile
import threading
from contextlib import closing
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from aurora.security.permissions import Permission

_EDIT_LOCK = threading.Lock()


def text_encoding(data):
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    return "utf-8-sig"


def sections(path):
    suffix = path.suffix.lower()
    if suffix == ".txt":
        data = path.read_bytes()
        for n, line in enumerate(data.decode(text_encoding(data)).splitlines(), 1):
            yield f"Строка {n}", line
    elif suffix == ".pdf":
        import pymupdf

        with pymupdf.open(path) as pdf:
            for n, page in enumerate(pdf, 1):
                yield f"Страница {n}", page.get_text()
    elif suffix == ".docx":
        from docx import Document
        from docx.text.paragraph import Paragraph

        for n, block in enumerate(Document(path).iter_inner_content(), 1):
            if isinstance(block, Paragraph):
                yield f"Абзац {n}", block.text
            else:
                for row, cells in enumerate(block.rows, 1):
                    yield f"Таблица {n}, строка {row}", " | ".join(c.text for c in cells.cells)
    elif suffix == ".xlsx":
        from openpyxl import load_workbook

        with closing(load_workbook(path, read_only=True, data_only=False)) as book:
            for sheet in book.worksheets:
                for n, row in enumerate(sheet.values, 1):
                    yield f"{sheet.title}, строка {n}", " | ".join(str(v) if v is not None else "" for v in row)
    else:
        raise ValueError("Неподдерживаемый формат документа.")


def read_document(path, query=None):
    needle = query.casefold() if query is not None else None
    output = []
    size = 0
    for location, text in sections(Path(path)):
        if not text.strip() or (needle is not None and needle not in text.casefold()):
            continue
        entry = f"{location}: {text}"
        remaining = 100_000 - size
        output.append(entry[:remaining])
        size += len(entry) + 1
        if size >= 100_000:
            output.append("Достигнут лимит предварительного просмотра.")
            break
    return "\n".join(output) or ("Совпадений нет." if needle else "Извлекаемый текст отсутствует.")


def append_text(path, text, modified_ns, size):
    from ctypes import WinDLL, WinError, get_last_error, wintypes

    target = Path(path)
    expected = (modified_ns, size)

    def check_version():
        stat = target.stat()
        if (stat.st_mtime_ns, stat.st_size) != expected:
            raise ValueError("Документ изменился. Выберите файл заново.")

    with _EDIT_LOCK:
        check_version()
        original = target.read_bytes()
        suffix = target.suffix.lower()
        if suffix == ".txt":
            value = original.decode(text_encoding(original))
            newline = "\r\n" if "\r\n" in value else "\n"
            addition = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
            if value and not value.endswith(("\r", "\n")):
                addition = newline + addition
            encoding = ("utf-16-le" if original.startswith(codecs.BOM_UTF16_LE) else
                        "utf-16-be" if original.startswith(codecs.BOM_UTF16_BE) else "utf-8")
            updated = original + addition.encode(encoding)
        elif suffix == ".docx":
            from docx import Document

            document = Document(BytesIO(original))
            document.add_paragraph(text)
            buffer = BytesIO()
            document.save(buffer)
            updated = buffer.getvalue()
        else:
            raise ValueError("Дописывание поддерживается для TXT и DOCX.")
        backup = target.with_name(f"{target.name}.{uuid4().hex}.bak")
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
            temp = Path(tmp.name)
        try:
            temp.write_bytes(updated)
            check_version()
            # Windows сохраняет заменяемую версию в backup в рамках одной операции.
            replace = WinDLL("kernel32", use_last_error=True).ReplaceFileW
            replace.argtypes = [wintypes.LPCWSTR] * 3 + [wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID]
            replace.restype = wintypes.BOOL
            if not replace(str(target), str(temp), str(backup), 0, None, None):
                raise WinError(get_last_error())
        finally:
            temp.unlink(missing_ok=True)
    return f"Текст добавлен. Резервная копия: {backup}"


def register_document_skills(registry):
    path_field = {"type": "string", "minLength": 1}
    for name, title, fields, permission, handler in (
        ("document.read", "Прочитать документ", {}, Permission.READ, read_document),
        ("document.search", "Найти текст в документе", {"query": path_field}, Permission.READ, read_document),
        ("document.append", "Добавить текст в конец документа",
         {"text": path_field, "modified_ns": {"type": "integer"}, "size": {"type": "integer", "minimum": 0}},
         Permission.MODIFY, append_text),
    ):
        properties = {"path": path_field, **fields}
        registry.register(name, title, {"type": "object", "properties": properties,
                          "required": list(properties), "additionalProperties": False}, permission, handler)
