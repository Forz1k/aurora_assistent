"""Реестр доверенных обработчиков. Внешний запрос содержит только имя и JSON-аргументы."""

import json
import logging
from copy import deepcopy
from datetime import datetime

from jsonschema import Draft202012Validator

from aurora.security.permissions import Permission, Permissions
from aurora.documents.files import register_document_skills
from aurora.skills.windows import register_windows_skills


class SkillError(ValueError):
    pass


class SkillRegistry:
    def __init__(self, permissions: Permissions):
        self._permissions = permissions
        self._entries = {}

    def register(self, name, title, schema, permission, handler):
        if name in self._entries:
            raise ValueError(f"Навык уже зарегистрирован: {name}")
        if not isinstance(permission, Permission) or not callable(handler):
            raise ValueError("Неверные права или обработчик навыка.")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            raise ValueError("Схема должна явно ограничивать допустимые аргументы.")
        Draft202012Validator.check_schema(schema)
        self._entries[name] = (title, Draft202012Validator(deepcopy(schema)), permission, handler)

    def catalog(self):
        return [(name, entry[0]) for name, entry in self._entries.items()]

    def execute(self, name, arguments, *, executor=None):
        if not isinstance(name, str) or name not in self._entries:
            logging.warning("Запрошен неизвестный навык")
            raise SkillError("Неизвестный навык.")
        title, validator, permission, handler = self._entries[name]
        try:
            encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False, allow_nan=False)
            values = json.loads(encoded)
        except (ValueError, TypeError, RecursionError) as error:
            raise SkillError("Ожидаются аргументы JSON.") from error
        if not validator.is_valid(values):
            logging.warning("Аргументы навыка %s отклонены", name)
            raise SkillError("Аргументы не соответствуют схеме навыка.")
        if not self._permissions.allows(name, title, permission, encoded):
            logging.info("Выполнение навыка %s отклонено", name)
            raise SkillError("Разрешение не получено.")
        if executor is not None:
            return executor.submit(self._invoke, name, title, handler, values)
        return self._invoke(name, title, handler, values)

    @staticmethod
    def _invoke(name, title, handler, values):
        try:
            result = handler(**values)
        except Exception as error:
            logging.error("Ошибка навыка %s: %s", name, type(error).__name__)
            raise SkillError(f"Не удалось выполнить навык «{title}».") from error
        logging.info("Выполнен навык %s", name)
        return result


def default_registry(permissions):
    registry = SkillRegistry(permissions)
    registry.register("local_time", "Местные дата и время",
                      {"type": "object", "properties": {}, "additionalProperties": False},
                      Permission.READ, lambda: datetime.now().astimezone().strftime("%d.%m.%Y %H:%M %z"))
    register_windows_skills(registry)
    register_document_skills(registry)
    return registry
