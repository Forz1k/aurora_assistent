from types import SimpleNamespace

import pytest

from aurora.memory.facts import Facts
from aurora.ui import chat


def test_explicit_memory_lifecycle(tmp_path, monkeypatch):
    local = Facts(tmp_path / "local.db")
    cloud = Facts(tmp_path / "cloud.db")
    assert local.read() == cloud.read() == ""

    def edit(value, accepted=True):
        monkeypatch.setattr(chat.QInputDialog, "getMultiLineText", lambda *args: (value, accepted))
        chat.ChatWindow.edit_facts(window)

    class Captured(Exception):
        pass

    def stream(model, messages):
        captured.extend(messages)
        raise Captured

    captured = []
    window = SimpleNamespace(facts=local, name="Ollama", status=SimpleNamespace(setText=lambda _: None),
                             send=SimpleNamespace(isEnabled=lambda: True),
                             input=SimpleNamespace(text=lambda: "Вопрос", setReadOnly=lambda _: None),
                             messages=[], system_prompt="Характер", provider=SimpleNamespace(stream=stream),
                             models=SimpleNamespace(currentText=lambda: "model"))
    edit(" Первый факт \n\nВторой факт")
    window.facts = Facts(local.path)
    assert window.facts.read() == "Первый факт\nВторой факт"
    edit("Отмена", False)
    with pytest.raises(Captured):
        chat.ChatWindow.submit(window)
    assert captured[0]["role"] == "system"
    assert captured[1]["role"] == "user" and "Второй факт" in captured[1]["content"]
    assert window.messages == []
    edit("Третий факт")
    with pytest.raises(ValueError):
        local.save("Первый факт\nВторой факт", "Устаревшее изменение")
    assert local.read() == "Третий факт"
    window.facts = cloud
    captured.clear()
    with pytest.raises(Captured):
        chat.ChatWindow.submit(window)
    assert len(captured) == 2 and cloud.read() == ""
    window.facts = local
    edit("")
    assert Facts(local.path).read() == ""
