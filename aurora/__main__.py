import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml

from aurora.providers.base import ProviderError
from aurora.providers.ollama_provider import OllamaProvider

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def load_settings(path: Path):
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or "log_level" not in data or set(data) - {"log_level", "microphone"}:
        raise ValueError("В настройках ожидается поле log_level.")
    if data["log_level"] not in LEVELS:
        raise ValueError("Допустимые значения log_level: " + ", ".join(LEVELS))
    if "microphone" in data and not isinstance(data["microphone"], str):
        raise ValueError("microphone должно содержать имя входного устройства.")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Тестовый запуск Авроры")
    parser.add_argument("--config", type=Path, default=ROOT / "config/settings.yaml")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--chat", action="store_true", help="Открыть чат")
    modes.add_argument("--list-models", action="store_true", help="Показать модели локальной Ollama")
    modes.add_argument("--list-mics", action="store_true", help="Показать входные аудиоустройства")
    modes.add_argument("--check-mic", action="store_true", help="Проверить захват и обнаружение речи")
    modes.add_argument("--transcribe", action="store_true", help="Записать и распознать русскую команду")
    modes.add_argument("--listen", action="store_true", help="Дождаться имени Аврора и записать команду")
    parser.add_argument("--device", type=int, help="Номер входа из --list-mics")
    parser.add_argument("--seconds", type=int, help="Длительность проверки от 1 до 60 секунд")
    args = parser.parse_args()
    if not (args.check_mic or args.transcribe or args.listen) and (args.device is not None or args.seconds is not None):
        parser.error("--device и --seconds используются с --check-mic, --transcribe или --listen")
    if args.seconds is not None and not 1 <= args.seconds <= 60:
        parser.error("--seconds: допустимо от 1 до 60")
    try:
        settings = load_settings(args.config)
        level = settings["log_level"]
        directory = ROOT / "logs"
        directory.mkdir(exist_ok=True)
        handler = RotatingFileHandler(directory / "aurora.log", maxBytes=1048576,
                                 backupCount=3, encoding="utf-8")
        logging.basicConfig(level=level, handlers=[handler],
                                format="%(asctime)s %(levelname)s %(message)s")
        if args.list_mics or args.check_mic or args.transcribe or args.listen:
            try:
                from aurora.audio.input import diagnose, select_device
                from sounddevice import PortAudioError
                try:
                    device = None if args.list_mics else select_device(args.device, settings.get("microphone"))
                    if args.listen:
                        from aurora.audio.wake import listen
                        try:
                            print(listen(device, args.seconds or 5))
                        except KeyboardInterrupt:
                            print("Ожидание остановлено.")
                        return 0
                    if args.transcribe:
                        from aurora.audio.stt import recognize_command
                        print(recognize_command(device, args.seconds or 5))
                        return 0
                except PortAudioError as error:
                    raise RuntimeError(str(error)) from error
                return diagnose(args.list_mics, device, args.seconds or 5)
            except (ImportError, OSError, RuntimeError, ValueError) as error:
                print(f"Ошибка аудиоввода: {error}", file=sys.stderr)
                return 1
        if args.chat:
            from aurora.ui.chat import run_chat
            return run_chat()
        if args.list_models:
            try:
                models = OllamaProvider().list_models()
            except ProviderError as error:
                logging.error("%s", error)
                print(error, file=sys.stderr)
                return 1
            logging.info("Получен список моделей Ollama: %d", len(models))
            print("\n".join(models) if models else "Ollama доступна. Список моделей пуст.")
            return 0
        logging.info("Тестовый запуск завершён.")
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        return 1
    print("Аврора: настройки и журнал готовы.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
