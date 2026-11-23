import pytest

from aurora.security.permissions import Decision, Permissions
from aurora.skills import windows
from aurora.skills.registry import SkillError, default_registry


@pytest.mark.parametrize("name,key", [
    ("windows.volume_up", windows.win32con.VK_VOLUME_UP),
    ("windows.volume_down", windows.win32con.VK_VOLUME_DOWN),
])
def test_volume_has_fixed_direction_and_requires_consent(monkeypatch, name, key):
    events = []
    monkeypatch.setattr(windows.win32api, "keybd_event", lambda *args: events.append(args))
    registry = default_registry(Permissions())
    with pytest.raises(SkillError):
        registry.execute(name, {})
    registry = default_registry(Permissions(lambda *_: Decision.ONCE))
    with pytest.raises(SkillError):
        registry.execute(name, {"key": 1})
    assert events == []
    registry.execute(name, {})
    assert events == [(key, 0, 0, 0), (key, 0, windows.win32con.KEYEVENTF_KEYUP, 0)]


def test_sound_settings_has_fixed_target(monkeypatch):
    targets = []
    monkeypatch.setattr(windows.os, "startfile", targets.append)
    registry = default_registry(Permissions(lambda *_: Decision.ONCE))
    with pytest.raises(SkillError):
        registry.execute("windows.sound_settings", {"uri": "other"})
    registry.execute("windows.sound_settings", {})
    assert targets == ["ms-settings:sound"]
