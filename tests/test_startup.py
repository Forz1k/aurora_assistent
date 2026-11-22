from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("settings,expected", [
    ("log_level: INFO", 0),
    ("log_level: verbose", 1),
    ("log_level: [", 1),
    ("[]", 1),
    (None, 1),
])
def test_startup(tmp_path, settings, expected):
    config = tmp_path / "settings.yaml"
    if settings is not None:
        config.write_text(settings, encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "aurora", "--config", str(config)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
    )
    assert result.returncode == expected
    if expected:
        assert result.stderr and b"Traceback" not in result.stderr
