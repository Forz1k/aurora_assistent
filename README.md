# Аврора

Тестовый запуск из корня проекта в PowerShell на Windows с Python 3.11 x64:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m aurora
.\.venv\Scripts\python -m pytest -q
~~~

Первую команду выполняйте при создании окружения. Для одного запуска достаточно зависимостей из requirements.txt. При успехе программа выводит «Аврора: настройки и журнал готовы.» и завершается с кодом 0. Параметр --config позволяет выбрать другой YAML-файл.
