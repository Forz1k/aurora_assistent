import pytest

from aurora.security.permissions import Decision, Permission, Permissions
from aurora.skills.registry import SkillError, SkillRegistry


@pytest.mark.parametrize("permission", [Permission.USER_ACTION, Permission.MODIFY, Permission.SENSITIVE])
def test_grants_are_scoped_and_sensitive_actions_require_each_confirmation(permission):
    decisions = iter([Decision.SESSION, Decision.DENY, Decision.ONCE])
    registry = SkillRegistry(Permissions(lambda *_: next(decisions)))
    calls = []
    schema = {"type": "object", "properties": {"item": {"type": "string", "minLength": 1}},
              "required": ["item"], "additionalProperties": False}
    registry.register("example", "Пример", schema, permission, lambda item: calls.append(item))
    if permission is Permission.SENSITIVE:
        with pytest.raises(SkillError):
            registry.execute("example", {"item": "a"})
        assert calls == []
    else:
        registry.execute("example", {"item": "a"})
        registry.execute("example", {"item": "a"})
        assert calls == ["a", "a"]
    with pytest.raises(SkillError):
        registry.execute("example", {"item": "b"})
    registry.execute("example", {"item": "b"})
    assert calls.count("b") == 1


def test_validation_precedes_permission_and_execution():
    def unexpected(*args, **kwargs):
        pytest.fail("Unexpected callback")

    registry = SkillRegistry(Permissions(unexpected))
    registry.register("example", "Пример", {"type": "object", "additionalProperties": False},
                      Permission.MODIFY, unexpected)
    for name, args in [("missing", {}), ("example", {"approved": True}), ("example", [])]:
        with pytest.raises(SkillError):
            registry.execute(name, args)


def test_protected_skill_without_ui_is_denied():
    registry = SkillRegistry(Permissions())
    registry.register("edit", "Изменение", {"type": "object", "additionalProperties": False},
                      Permission.MODIFY, lambda: pytest.fail("Executed"))
    with pytest.raises(SkillError):
        registry.execute("edit", {})
