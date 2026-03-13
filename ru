Интеграция для управления камерами на прошивке OpenIPC, Beward и Vivotek в Home Assistant с мощным веб-интерфейсом для расширенных возможностей.

## ✨ Возможности

### 📹 Видеонаблюдение
- RTSP-потоки и снимки
- Запись в медиа-папку HA с OSD наложением
- Управление PTZ для Vivotek
- Управление реле для Beward

### 📊 Мониторинг
- Температура CPU, FPS, битрейт
- Статус SD-карты, сетевая статистика
- Распознавание номеров (LNPR) для Beward

### 🔊 Голосовые оповещения (TTS)
- **Google TTS** - облачный синтез речи
- **RHVoice** - локальный синтез (голос Анна) через отдельный аддон
- Поддержка Beward (A-law) и OpenIPC (PCM)

### 📱 Уведомления
- Отправка фото и видео в Telegram
- Визуальный конструктор уведомлений

### ➕ НОВИНКИ (Март 2026)

#### 🖥️ **OpenIPC Bridge Addon** с веб-интерфейсом
- Управление камерами через красивый UI
- Импорт камер из интеграции OpenIPC
- Настройка OSD с предпросмотром и перетаскиванием
- Генератор QR-кодов с отправкой в Telegram
- Выбор TTS провайдера (Google/RHVoice)

#### 🎨 **Визуальный редактор OSD**
- Перетаскивание регионов мышкой
- Предпросмотр в реальном времени
- Сохранение и загрузка шаблонов
- Поддержка логотипов (BMP)

#### 📸 **QR-сканер и генератор**
- Непрерывное сканирование QR-кодов
- Генерация QR-кодов с кастомизацией
- История сканирований с экспортом в CSV
- Отправка QR в Telegram

#### 🔄 **Универсальный блюпринт**
- Запись видео при открытии двери
- Динамический OSD с тикающими часами
- Выбор TTS провайдера
- Отправка в Telegram

---

## 📦 Установка

### 1. OpenIPC Bridge Addon (Обязателен для новых функций)

```bash
# Добавьте репозиторий в Supervisor:
# Настройки → Аддоны → Магазин аддонов → ⋮ → Репозитории
# Добавьте: https://github.com/OpenIPC/hass
После установки аддон будет доступен по адресу http://[IP-вашего-HA]:5000

2. Интеграция OpenIPC
Через HACS (рекомендуется)
Откройте HACS → Интеграции → ⋮ → Пользовательские репозитории

Добавьте https://github.com/OpenIPC/hass с категорией Интеграция

Найдите "OpenIPC Camera" и установите

Перезапустите HA

Вручную
Скопируйте папку custom_components/openipc в /config/custom_components/ и перезапустите HA.

🎮 Использование веб-интерфейса аддона
После установки откройте http://[IP-вашего-HA]:5000. Вы увидите главную страницу с дашбордом.

📹 Вкладка "Камеры"
Импорт из Home Assistant
Нажмите кнопку "Импортировать камеры из HA" - аддон автоматически подтянет все камеры из интеграции OpenIPC с правильными настройками в зависимости от типа:

🟦 OpenIPC - стандартные IP-камеры

🟩 Beward - домофоны с реле

🟨 Vivotek - PTZ-камеры

Ручное добавление
Если нужно добавить камеру вручную, заполните форму:

Название - понятное имя

IP адрес - например, 192.168.1.4

Тип - OpenIPC/Beward/Vivotek

Логин/пароль - данные для доступа

🖥️ Вкладка "OSD" (On-Screen Display)
Визуальный редактор для наложения текста на видео:

Выберите камеру из списка

Настройте регионы (до 4х):

Регион 0 - для логотипа (BMP)

Регионы 1-3 - для текста

Перетаскивайте мышкой - позиция меняется в реальном времени

Настройте внешний вид:

Цвет текста (RGB палитра)

Размер шрифта (8-72 px)

Шрифт (Ubuntu Mono, Arial, Times)

Прозрачность (0-255)

Используйте переменные:

$t - текущее время (тикает!)

$B - битрейт

$C - счетчик кадров

$M - использование памяти

Сохраняйте шаблоны для быстрого применения

Примеры OSD:
text
Регион 1: "🚪 ДВЕРЬ ОТКРЫТА! 13.03.2026 15:23:45" (красный, 48px)
Регион 2: "⏺️ ЗАПИСЬ: 3 МИНУТЫ" (желтый, 36px)
Регион 3: "⏱️ 15:23:45" (зеленый, 32px) - тикающие часы
📸 Вкладка "QR-сканер и генератор"
Сканер
Выберите камеру

Настройте ожидаемый код (опционально)

Нажмите "Начать сканирование"

При обнаружении QR-кода в HA генерируется событие openipc_qr_detected

Генератор
Введите текст или URL

Настройте размер, цвета, уровень коррекции

Нажмите "Сгенерировать"

"Сохранить в файл" или "Отправить в Telegram"

История
Все сканирования сохраняются

Экспорт в CSV

Копирование кода в буфер

Быстрая генерация QR из истории

🔊 Вкладка "TTS" (Text-to-Speech)
Настройка голосовых уведомлений с поддержкой разных провайдеров:

Доступные провайдеры:
Google TTS - облачный, 30+ языков, высокое качество

RHVoice - локальный, без интернета, голос "Анна" (требуется отдельный аддон)

Как использовать:
Выберите камеру

Выберите провайдера

Выберите язык

Введите текст

Нажмите "Протестировать"

Проверка работы:
При успехе - зеленое уведомление

Отладочные файлы сохраняются в /config/www/tts_debug_*.pcm

🤖 Блюпринты
Блюпринт 1: QR-сканер (готовый в репозитории)
yaml
# URL для импорта:
https://github.com/OpenIPC/hass/blob/main/blueprints/automation/openipc/qr_scanner.yaml
Создает автоматизацию, которая запускает сканирование по нажатию кнопки, проверяет код и выполняет действия:

TTS уведомление

Управление реле

Отправка в Telegram

Блюпринт 2: Запись видео при открытии двери (НОВЫЙ!)
yaml
# URL для импорта:
https://github.com/OpenIPC/hass/blob/main/blueprints/automation/openipc/door_recording.yaml
Универсальная автоматизация с расширенными возможностями:

Настройки:
Датчик двери - любой binary_sensor с device_class door

Камера - OpenIPC камера

Медиа-плеер - динамик камеры

TTS провайдер - Google или RHVoice

Длительность записи - от 10 до 600 секунд

Регионы OSD - выбор номеров для текста

Telegram - включение/выключение отправки

Время после записи - сколько секунд показывать тикающие часы

Что делает:
Очищает старый OSD

TTS: "Дверь открыта, начинаю запись" (выбранный провайдер)

Устанавливает OSD с датой и временем (с тикающими часами!)

Записывает видео заданной длительности

После записи показывает тикающее время на экране

TTS: "Запись завершена"

Отправляет видео в Telegram (если включено)

TTS: "Видео отправлено в Telegram"

Очищает экран

Пример OSD во время записи:
text
🚪 ДВЕРЬ ОТКРЫТА! 13.03.2026
⏺️ ЗАПИСЬ: 3 МИНУТЫ
Пример OSD после записи:
text
13.03.2026
⏱️ 15:23:45  (тикает!)
📝 Примеры автоматизаций
Простое TTS-уведомление
yaml
alias: "Сказать 'Привет' при движении"
trigger:
  - platform: state
    entity_id: binary_sensor.openipc_sip_motion
    to: "on"
action:
  - service: media_player.play_media
    target:
      entity_id: media_player.openipc_sip_speaker
    data:
      media_content_id: "Привет, вы в кадре!"
      media_content_type: "tts"
      extra:
        provider: "rhvoice"  # или "google"
TTS с выбором провайдера через переменную
yaml
alias: "TTS с динамическим выбором"
variables:
  use_rhvoice: true  # переключайте здесь
action:
  - service: media_player.play_media
    target:
      entity_id: media_player.openipc_sip_speaker
    data:
      media_content_id: "Внимание, обнаружено движение"
      media_content_type: "tts"
      extra:
        provider: "{{ 'rhvoice' if use_rhvoice else 'google' }}"
QR-скан для управления воротами
yaml
alias: "Открыть ворота по QR-коду"
trigger:
  - platform: event
    event_type: openipc_qr_detected
condition:
  - condition: template
    value_template: "{{ trigger.event.data.data == 'секретный_код' }}"
action:
  - service: switch.turn_on
    entity_id: switch.gate_relay
  - delay:
      seconds: 1
  - service: switch.turn_off
    entity_id: switch.gate_relay
  - service: media_player.play_media
    target:
      entity_id: media_player.openipc_sip_speaker
    data:
      media_content_id: "Доступ разрешен, ворота открыты"
      media_content_type: "tts"
🔧 Настройка RHVoice (локальный TTS)
Для использования RHVoice установите отдельный аддон:

Добавьте репозиторий: https://github.com/definitio/ha-rhvoice-addon

Установите аддон RHVoice Home Assistant

Установите интеграцию RHVoice через HACS

В настройках интеграции укажите host: localhost

После этого RHVoice будет доступен в нашем блюпринте и веб-интерфейсе.

📊 Структура проекта
text
/
├── custom_components/openipc/     # Интеграция для HA
│   ├── __init__.py
│   ├── api.py
│   ├── api_ha.py                  # API для аддона
│   ├── beward_device.py
│   ├── binary_sensor.py
│   ├── button.py
│   ├── camera.py
│   ├── commands.py
│   ├── config_flow.py
│   ├── const.py
│   ├── coordinator.py
│   ├── diagnostics.py
│   ├── discovery.py
│   ├── helpers.py
│   ├── lnpr.py
│   ├── media_player.py
│   ├── migration.py
│   ├── notify.py
│   ├── onvif_client.py
│   ├── openipc_audio.py
│   ├── osd_manager.py
│   ├── parsers.py
│   ├── ptz.py
│   ├── ptz_entity.py
│   ├── qr_scanner.py
│   ├── qr_utils.py
│   ├── recorder.py
│   ├── recording.py
│   ├── select.py
│   ├── sensor.py
│   ├── services.py
│   ├── services_impl.py
│   ├── switch.py
│   ├── vivotek_device.py
│   ├── vivotek_ptz.py
│   └── vivotek_ptz_entities.py
│
├── addon/                          # OpenIPC Bridge Addon
│   ├── Dockerfile
│   ├── config.yaml
│   ├── run.sh
│   ├── server.py
│   ├── tts_generate_openipc.sh
│   ├── tts_generate.sh
│   ├── tts_generate_rhvoice.sh     # Новый скрипт для RHVoice
│   ├── check_modules.py
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── config.html
│       ├── osd.html                # Визуальный редактор OSD
│       ├── qr.html                 # QR-сканер и генератор
│       └── tts.html                # TTS с выбором провайдера
│
└── blueprints/automation/openipc/
    ├── qr_scanner.yaml             # Существующий блюпринт
    └── door_recording.yaml         # НОВЫЙ блюпринт с выбором TTS
🆘 Поддержка и устранение неполадок
Логи
Интеграция: Настройки → Система → Логи → openipc

Аддон: Supervisor → OpenIPC Bridge → Логи

Отладка TTS: проверьте /config/www/tts_debug_*.pcm

Частые проблемы
OSD не появляется
Проверьте, что на камере запущен OSD сервис (ps | grep osd)

Проверьте доступность порта 9000 (netstat -tlnp | grep 9000)

В веб-интерфейсе OSD проверьте настройки прозрачности (opacity: 255)

TTS не работает
Проверьте доступность камеры (ping)

Проверьте правильность эндпоинта (/play_audio для OpenIPC)

Для RHVoice: убедитесь, что отдельный аддон запущен

Импорт камер из HA не работает
Проверьте, что в manifest.json есть зависимость http

Проверьте эндпоинт: http://[HA_IP]:8123/api/openipc/cameras

🤝 Как помочь проекту
⭐ Поставьте звезду на GitHub

🐛 Сообщайте об ошибках в Issues

📝 Улучшайте документацию

🔧 Отправляйте Pull Request

📜 Лицензия
MIT License

OpenIPC Community - делаем умный дом доступнее! 🚀
