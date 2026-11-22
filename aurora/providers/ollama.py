import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class OllamaError(Exception):
    """Не удалось получить список моделей."""


def list_models(base_url: str = "http://127.0.0.1:11434") -> list[str]:
    try:
        with urlopen(base_url.rstrip("/") + "/api/tags", timeout=5) as response:
            data = json.load(response)
    except HTTPError as error:
        raise OllamaError(f"Ollama вернула HTTP {error.code}.") from error
    except (URLError, OSError, HTTPException) as error:
        raise OllamaError(f"Нет связи с Ollama ({base_url}). Проверьте запуск ollama serve.") from error
    except ValueError as error:
        raise OllamaError("Некорректный JSON в ответе Ollama.") from error

    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise OllamaError("В ответе Ollama отсутствует список models.")
    names = []
    for model in data["models"]:
        name = model.get("name") if isinstance(model, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise OllamaError("В ответе Ollama обнаружена модель без имени.")
        names.append(name)
    return names
