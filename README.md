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

В окне чата нажмите «Провайдер…». Для OpenAI выберите OpenAI, введите идентификатор доступной вашему аккаунту текстовой модели и API-ключ, затем нажмите кнопку сохранения. При повторной настройке оставьте поле ключа пустым, чтобы использовать сохранённый ключ. Новый ключ заменит прежний в записи Aurora/OpenAI диспетчера учётных данных Windows текущего пользователя. Там же запись можно удалить.

Название провайдера и модель сохраняются в data/chat.ini. Локальная история остаётся в data/chat.sqlite3, облачная хранится отдельно в data/chat-openai.sqlite3. Для возврата к локальной беседе выберите Ollama.
## Проверка микрофона

Из корня проекта в PowerShell:

~~~powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m aurora --list-mics
.\.venv\Scripts\python -m aurora --check-mic --device 2 --seconds 5
~~~

Подставьте актуальный номер из списка. Без --device выбирается fifine по имени microphone в config/settings.yaml. При отсутствии этой настройки используется системный вход. Список Windows показывает входы одного аудиоинтерфейса, с предпочтением MME. Произнесите фразу во время проверки. Команда сообщает число полученных блоков и длительность речи по оценке Silero VAD. Звук обрабатывается в памяти на CPU.

Для распознавания русской команды запустите:

~~~powershell
.\.venv\Scripts\python -m aurora --transcribe --seconds 5
~~~

Говорите после приглашения. После записи команда проверяет наличие речи и выводит распознанный текст. При первом использовании faster-whisper загружает многоязычную модель base в локальный кеш Hugging Face. Распознавание выполняется на CPU INT8, звук остаётся в памяти.

Для активации голосом запустите:

~~~powershell
.\.venv\Scripts\python -m aurora --listen
~~~

Назовите «Аврора» отдельным словом, сделайте паузу и дождитесь приглашения «Произнесите команду». После записи программа выводит текст и завершает сеанс. Ожидание имени можно прервать Ctrl+C. Параметр --seconds задаёт длительность записи команды (по умолчанию 5 секунд). Используется выбранный fifine; --device позволяет выбрать другой вход. Во время ожидания Vosk непрерывно проверяет звук на CPU. При первом запуске нужна русская модель vosk-model-small-ru-0.22: Аврора ищет её в data или кеше Vosk, затем при необходимости Vosk скачивает модель. После активации следующую команду распознаёт faster-whisper.

### Голосовая команда в чате

Запустите чат командой `.\.venv\Scripts\python -m aurora --chat`. Выберите модель, оставьте поле сообщения пустым и нажмите «Голос». При статусе «Скажите „Аврора“» произнесите имя и дождитесь приглашения записать команду. После пяти секунд записи чат распознаёт речь и автоматически отправляет текст текущему провайдеру. При выборе OpenAI распознавание выполняется локально, а текст команды и история облачной беседы передаются в OpenAI.

Кнопка «Остановить» доступна во время ожидания имени, записи, распознавания и получения ответа. После завершения можно отправить текст или снова нажать «Голос».

### Озвучивание ответов

В чате включите «Озвучивать ответы» и выберите женский голос рядом с флажком. При установке Qwen3-TTS-12Hz-1.7B-Base с речевым образцом первым предлагается «Аврора · живая речь». Она использует тембр и ритм записанной русской реплики. Профиль VoiceDesign «Аврора · разговорный» также доступен при установке его модели. Он синтезирует русскую речь на CPU по описанию женского тембра и интонации, с частотой 24 кГц. Первый ответ требует загрузки модели и генерации; повторные фрагменты воспроизводятся из кеша. Для меньшей задержки можно выбрать Xenia, Kseniya или Баю. Выбор сохраняется между запусками, кнопка «Остановить» прерывает речь. Для ответов любого провайдера синтез выполняется локально в отдельном процессе на CPU. Модель Silero v5_6_ru сама расставляет ударения, восстанавливает «ё» и учитывает тип предложения. Частота вывода — 48 кГц.

Для новой установки нужны зависимости из requirements.txt и модель из официального каталога Silero. Выполните один раз из корня проекта:

~~~powershell
New-Item -ItemType Directory -Force data/voices | Out-Null
curl.exe --fail --location https://models.silero.ai/models/tts/ru/v5_6_ru.pt --output data/voices/v5_6_ru.pt
Get-FileHash data/voices/v5_6_ru.pt -Algorithm SHA256
~~~

SHA-256 проверенной версии: 04CC9B1D08CE38BCAA9D02C488D80D3E6806D17F7EAA7C95982F36A3CBF50B2E.

Готовые фрагменты хранятся в data/tts-cache.sqlite3 отдельно по голосу и версии модели. Лимит аудиоданных — 64 МиБ. Пока кеш доступен, повторная фраза воспроизводится без загрузки модели. Если выбранная модель не может синтезировать фрагмент, используется локальный резервный Piper. Для новой установки резервного голоса:

~~~powershell
.\.venv\Scripts\python -m piper.download_voices --download-dir data/voices ru_RU-irina-medium
~~~

#### Установка разговорного голоса на новой машине

Из корня проекта в PowerShell используйте отдельное окружение моделей. Первые две команды нужны при его создании:

~~~powershell
python -m venv data/voice-studio/qwen-env
data/voice-studio/qwen-env/Scripts/python.exe -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
$qwen = "data/voice-studio/qwen-env/Scripts/python.exe"
& $qwen -m pip install qwen-tts==0.1.1 sounddevice==0.5.3 piper-tts==1.4.2
& $qwen -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',revision='5ecdb67327fd37bb2e042aab12ff7391903235d3',local_dir='data/voice-studio/qwen-design')"
~~~

Для профиля «Аврора · живая речь» в том же окружении скачайте веса Base:

~~~powershell
& $qwen -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-1.7B-Base',revision='fd4b254389122332181a7c3db7f27e918eec64e3',local_dir='data/voice-studio/qwen-natural')"
~~~

Для воспроизведения профиля нужен также локальный WAV из Voice Studio, указанный в aurora/tts/natural.py. Модель получает расшифровку образца, полную фразу ответа и её пунктуацию. Произнесённые образцы хранятся в кеше отдельно от VoiceDesign.

После загрузки файлов перезапустите чат. Оба профиля работают офлайн. Настройки VoiceDesign находятся в aurora/tts/design.py, параметры голоса по записи — в aurora/tts/natural.py.

### Aurora Voice Studio · подготовка реплик

Из корня проекта укажите путь к видео и новую папку результата:

~~~powershell
.\.venv\Scripts\python -m aurora.tts.studio "D:\загрузки\videoplayback.mpg4" "data\voice-studio\hush"
~~~

В source.wav находится полная первая аудиодорожка, в clips — её фрагменты по границам речи Silero VAD. Откройте review.html для прослушивания. В manifest.csv можно исправить черновой текст, отметить слышимые эффекты, другого говорящего или обрезанные слова и поменять статус проверенной строки. Время указано в секундах от начала аудиодорожки. Редактируемый реестр — manifest.csv; страница прослушивания показывает исходную автоматическую расшифровку.

### Сравнение голосов на CPU

Для контрольного Piper используйте основное окружение. Для Qwen используйте отдельное окружение, чтобы его PyTorch и Transformers не меняли зависимости чата. Стенд рассчитан на Windows x64 и Python 3.11. Для повторения эксперимента из корня проекта:

~~~powershell
python -m venv data/voice-studio/qwen-env
$qwen = "data/voice-studio/qwen-env/Scripts/python.exe"
& $qwen -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
& $qwen -m pip install qwen-tts==0.1.1 soundfile psutil
& $qwen -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-Base', revision='5d83992436eae1d760afd27aff78a71d676296fc', local_dir='data/voice-studio/qwen-base')"
$ref = "data/voice-studio/hush/clips/0280.wav"
$dest = "data/voice-studio/repeat"
.\.venv\Scripts\python -m aurora.tts.benchmark piper "$dest/piper.wav"
& $qwen -m aurora.tts.benchmark qwen-vector "$dest/vector.wav" --reference $ref
& $qwen -m aurora.tts.benchmark qwen-icl "$dest/icl.wav" --reference $ref --transcript "А теперь я так живу. Вот она слава."
~~~

Для каждого прогона стенд сохраняет WAV и JSON с длительностью, временем загрузки, временем синтеза и пиковым рабочим набором процесса. RTF равен времени синтеза, делённому на длительность результата. Используйте новую папку для каждого повторения.
