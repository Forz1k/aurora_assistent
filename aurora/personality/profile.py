import logging
from pathlib import Path

import yaml


PROFILE = Path(__file__).resolve().parents[2] / "config/personality.yaml"


def load_prompt(path: Path = PROFILE) -> str:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        prompt = data.get("system_prompt") if isinstance(data, dict) else None
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Ожидается непустой текст system_prompt.")
        return prompt.strip()
    except (OSError, ValueError, yaml.YAMLError) as error:
        logging.warning("Профиль характера %s недоступен: %s", path, type(error).__name__)
        return ""
