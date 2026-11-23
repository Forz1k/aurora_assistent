"""Разрешённые действия Windows, доступные через меню навыков."""

import os
from functools import partial

import win32api
import win32con

from aurora.security.permissions import Permission


def memory_status():
    memory = win32api.GlobalMemoryStatusEx()
    return (f"Оперативная память: доступно {memory['AvailPhys'] / 2**30:.1f} "
            f"из {memory['TotalPhys'] / 2**30:.1f} ГиБ.")


def open_sound_settings():
    os.startfile("ms-settings:sound")
    return "Windows приняла запрос на открытие параметров звука."


def change_volume(key):
    win32api.keybd_event(key, 0, 0, 0)
    win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
    return "Команда изменения громкости отправлена Windows."


def register_windows_skills(registry):
    no_args = {"type": "object", "properties": {}, "additionalProperties": False}
    for name, title, permission, handler in (
        ("windows.memory", "Доступная оперативная память", Permission.READ, memory_status),
        ("windows.sound_settings", "Открыть параметры звука", Permission.USER_ACTION, open_sound_settings),
        ("windows.volume_up", "Прибавить громкость на один шаг", Permission.MODIFY,
         partial(change_volume, win32con.VK_VOLUME_UP)),
        ("windows.volume_down", "Убавить громкость на один шаг", Permission.MODIFY,
         partial(change_volume, win32con.VK_VOLUME_DOWN)),
    ):
        registry.register(name, title, no_args, permission, handler)
