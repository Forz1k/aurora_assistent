import codecs

import pymupdf
import pytest
from docx import Document
from openpyxl import Workbook

from aurora.security.permissions import Decision, Permissions
from aurora.skills.registry import SkillError, default_registry


@pytest.mark.parametrize("suffix", [".txt", ".docx", ".pdf", ".xlsx"])
def test_read_and_search(tmp_path, suffix):
    path = tmp_path / ("document" + suffix)
    if suffix == ".txt":
        path.write_text("Hello World", encoding="utf-8-sig")
    elif suffix == ".docx":
        doc = Document()
        doc.add_table(rows=1, cols=1).cell(0, 0).text = "Hello World"
        doc.save(path)
    elif suffix == ".xlsx":
        book = Workbook()
        book.active.append(["Hello World"])
        book.save(path)
    else:
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((72, 72), "Hello World")
            pdf.save(path)
    registry = default_registry(Permissions())
    assert "Hello World" in registry.execute("document.read", {"path": str(path)})
    assert "Hello World" in registry.execute("document.search", {"path": str(path), "query": "WORLD"})
    assert "Совпадений нет" in registry.execute("document.search", {"path": str(path), "query": "Missing"})


@pytest.mark.parametrize("suffix", [".txt", ".docx"])
def test_append_requires_permission_and_backs_up_original(tmp_path, suffix):
    path = tmp_path / ("sample" + suffix)
    if suffix == ".txt":
        path.write_bytes(codecs.BOM_UTF16_BE + "Один\r\nДва".encode("utf-16-be"))
    else:
        doc = Document()
        doc.add_paragraph("Один").runs[0].bold = True
        doc.save(path)
    before = path.read_bytes()
    args = dict(path=str(path), text="Три", modified_ns=path.stat().st_mtime_ns, size=len(before))
    with pytest.raises(SkillError):
        default_registry(Permissions()).execute("document.append", args)
    assert list(tmp_path.iterdir()) == [path] and path.read_bytes() == before
    registry = default_registry(Permissions(lambda *_: Decision.ONCE))
    registry.execute("document.append", args)
    assert next(tmp_path.glob("*.bak")).read_bytes() == before
    if suffix == ".txt":
        assert path.read_bytes() == before + "\r\nТри".encode("utf-16-be")
    else:
        doc = Document(path)
        assert doc.paragraphs[0].runs[0].bold
        assert doc.paragraphs[-1].text == "Три"
    with pytest.raises(SkillError):
        registry.execute("document.append", args)
