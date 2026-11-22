import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def load_level(path: Path) -> str:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or set(data) != {"log_level"}:
        raise ValueError("В настройках ожидается поле log_level.")
    if data["log_level"] not in LEVELS:
        raise ValueError("Допустимые значения log_level: " + ", ".join(LEVELS))
    return data["log_level"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Тестовый запуск Авроры")
    parser.add_argument("--config", type=Path, default=ROOT / "config/settings.yaml")
    args = parser.parse_args()
    try:
        level = load_level(args.config)
        directory = ROOT / "logs"
        directory.mkdir(exist_ok=True)
        handler = RotatingFileHandler(directory / "aurora.log", maxBytes=1048576,
                                 backupCount=3, encoding="utf-8")
        logging.basicConfig(level=level, handlers=[handler],
                                format="%(asctime)s %(levelname)s %(message)s")
        logging.info("Тестовый запуск завершён.")
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        return 1
    print("Аврора: настройки и журнал готовы.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
