from typing import Protocol

from PySide6.QtCore import QObject, Signal


class ProviderError(Exception):
    """Ошибка запроса к LLM-провайдеру."""


class ChatStream(QObject):
    """Сигналы поступают в цикле Qt после возврата из stream()."""

    chunk = Signal(str)
    finished = Signal(str)  # Пустая строка при успехе, сообщение при ошибке или отмене.

    def cancel(self) -> None:
        raise NotImplementedError


class LLMProvider(Protocol):
    def list_models(self) -> list[str]:
        """Блокирующий вызов для рабочего потока. При ошибке вызывает ProviderError."""
        ...

    def stream(self, model: str, messages: list[dict[str, str]]) -> ChatStream:
        """Запускает запрос в потоке Qt. Завершает поток одним сигналом finished."""
        ...
