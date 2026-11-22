# Аврора

Тестовый запуск из корня проекта в PowerShell на Windows с Python 3.11 x64:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m aurora
.\.venv\Scripts\python -m pytest -q
~~~

Первую команду выполняйте при создании окружения. Для одного запуска достаточно зависимостей из requirements.txt. При успехе программа выводит «Аврора: настройки и журнал готовы.» и завершается с кодом 0. Параметр --config позволяет выбрать другой YAML-файл.

Для получения списка моделей запустите Ollama (или выполните `ollama serve` в отдельном терминале), затем из корня проекта:
~~~powershell
.\.venv\Scripts\python -m aurora --list-models
~~~
Для запуска окна чата из корня проекта:

~~~powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m aurora --chat
~~~

При запущенной Ollama выберите модель и отправьте сообщение кнопкой или клавишей Enter. После запуска недоступного сервера нажмите «Обновить». Ответ появляется по мере генерации. Кнопка «Остановить» прерывает запрос и оставляет вопрос в поле ввода для повторной отправки. Завершённые пары сообщений сохраняются в data/chat.sqlite3 и восстанавливаются при запуске чата.
