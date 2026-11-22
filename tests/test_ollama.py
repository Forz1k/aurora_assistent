from io import BytesIO

import pytest

from aurora.providers import ollama


@pytest.mark.parametrize(("body", "expected"), [
    (b'{"models":[{"name":"qwen:test"}]}', ["qwen:test"]),
    (b'{"models":[]}', []),
    (b'{}', None),
    (b'{"models":[{}]}', None),
    (b'invalid', None),
])
def test_list_models(monkeypatch, body, expected):
    def respond(url, timeout):
        assert url == "http://127.0.0.1:11434/api/tags"
        assert timeout > 0
        return BytesIO(body)

    monkeypatch.setattr(ollama, "urlopen", respond)
    if expected is None:
        with pytest.raises(ollama.OllamaError):
            ollama.list_models()
    else:
        assert ollama.list_models() == expected
