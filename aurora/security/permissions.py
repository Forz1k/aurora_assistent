"""Разрешения окна Авроры. Грант относится к навыку и точным аргументам."""

from enum import Enum, auto


class Permission(Enum):
    READ = auto()
    USER_ACTION = auto()
    MODIFY = auto()
    SENSITIVE = auto()  # Удаление, передача конфиденциальных данных, администрирование.


class Decision(Enum):
    DENY = auto()
    ONCE = auto()
    SESSION = auto()


class Permissions:
    def __init__(self, confirm=None):
        self._confirm = confirm
        self._grants = set()

    def allows(self, name, title, permission, arguments_json):
        if permission is Permission.READ:
            return True
        reusable = permission in (Permission.USER_ACTION, Permission.MODIFY)
        key = (name, arguments_json)
        if reusable and key in self._grants:
            return True
        if self._confirm is None:
            return False
        decision = self._confirm(title, arguments_json, reusable)
        if decision is Decision.SESSION and reusable:
            self._grants.add(key)
            return True
        return decision is Decision.ONCE
