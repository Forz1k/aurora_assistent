import json
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(Exception):
    """Ошибка обращения к Ollama."""


def _request(request, timeout):
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        raise OllamaError(f"Ollama вернула HTTP {error.code}.") from error
    except (URLError, OSError, HTTPException) as error:
        raise OllamaError("Нет связи с Ollama. Проверьте запуск ollama serve.") from error
    except ValueError as error:
        raise OllamaError("Некорректный JSON в ответе Ollama.") from error

def list_models(base_url: str = "http://127.0.0.1:11434") -> list[str]:
    data = _request(base_url.rstrip("/") + "/api/tags", 5)
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise OllamaError("В ответе Ollama отсутствует список models.")
    names = []
    for model in data["models"]:
        name = model.get("name") if isinstance(model, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise OllamaError("В ответе Ollama обнаружена модель без имени.")
        names.append(name)
    return names


def chat(model: str, messages: list[dict[str, str]]) -> str:
    payload = {"model": model, "messages": messages, "stream": False}
    request = Request("http://127.0.0.1:11434/api/chat",
                      data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json"})
    data = _request(request, 180)
    message = data.get("message") if isinstance(data, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("Ollama вернула ответ без текста.")
    return content
