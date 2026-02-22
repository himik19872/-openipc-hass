🎨 Шрифты для OSD
Для работы OSD необходимо добавить TTF шрифты:

bash
# Создайте папку для шрифтов
mkdir -p /config/custom_components/openipc/openipc_fonts

# Скачайте шрифты (пример)
/config/custom_components/openipc/openipc_fonts
DejaVuSans.ttf
DejaVuSans-Bold.ttf
Проверьте доступные шрифты:

yaml
service: openipc.list_fonts
🚀 Сервисы
Основные сервисы
Сервис	Описание
openipc.record_with_osd	Запись видео с наложением текста
openipc.record_and_send_telegram	Запись и отправка в Telegram
openipc.timed_recording	Запись на указанное время
openipc.get_recordings	Список записей
openipc.delete_recording	Удаление записи
openipc.diagnose_rtsp	Диагностика RTSP потока
openipc.diagnose_telegram	Диагностика Telegram
openipc.list_fonts	Список доступных шрифтов
Пример использования
yaml
service: openipc.record_with_osd
target:
  entity_id: camera.192_168_1_100
data:
  duration: 60
  template: |
    ⏰ {{ now().strftime('%H:%M:%S') }}
    📅 {{ now().strftime('%Y-%m-%d') }}
    ===================
    🎥 {camera_name}
    🌡️ CPU: {cpu_temp}°C
    📊 FPS: {fps}
    ===================
    Запись: 60 сек
  position: bottom_left
  font_size: 14
  color: yellow
  send_telegram: true
📝 Примеры автоматизаций
Запись при открытии окна
yaml
alias: Запись при открытии окна
description: Запись видео при открытии окна
trigger:
  - platform: state
    entity_id: binary_sensor.living_window
    to: "on"
    for:
      seconds: 1
variables:
  temp: "{{ states('sensor.temperature') | float(0) }}"
action:
  - service: openipc.record_with_osd
    target:
      entity_id: camera.192_168_1_100
    data:
      duration: 60
      template: |
        ⏰ {{ now().strftime('%H:%M:%S') }}
        📅 {{ now().strftime('%Y-%m-%d') }}
        ===================
        🪟 Окно: 🟢 ОТКРЫТО
        🌡️ Температура: {{ temp }}°C
        ===================
        Запись: 60 сек
      position: bottom_left
      font_size: 14
      color: yellow
      send_telegram: true
mode: single
Запись при движении
yaml
alias: Запись при движении
description: Запись видео при обнаружении движения
trigger:
  - platform: state
    entity_id: binary_sensor.openipc_camera_motion
    to: "on"
action:
  - service: openipc.record_with_osd
    target:
      entity_id: camera.192_168_1_100
    data:
      duration: 30
      template: |
        ⚠️ ДВИЖЕНИЕ!
        ⏰ {{ now().strftime('%H:%M:%S') }}
        🌡️ CPU: {cpu_temp}°C
        📊 FPS: {fps}
      position: top_left
      font_size: 16
      color: red
      send_telegram: true
mode: single
📋 Доступные переменные для шаблона OSD
Переменная	Описание
{camera_name}	Имя камеры
{timestamp}	Текущее время
{cpu_temp}	Температура CPU
{uptime}	Время работы
{fps}	FPS видео
{bitrate}	Битрейт
{resolution}	Разрешение
{wifi_signal}	Сигнал WiFi
{motion}	Статус движения
{recording}	Статус записи
🔧 Диагностика
Проверка RTSP
yaml
service: openipc.diagnose_rtsp
target:
  entity_id: camera.192_168_1_100
Проверка Telegram
yaml
service: openipc.diagnose_telegram
target:
  entity_id: camera.192_168_1_100
📋 Требования
Home Assistant 2023.8.0 или новее

ffmpeg (для записи видео)

Камера на прошивке OpenIPC

📄 Лицензия
MIT License

👤 Автор
himik19872 - GitHub

⭐ Поддержка
Если вам нравится эта интеграция, поставьте звезду на GitHub!

https://img.shields.io/github/stars/himik19872/openipc-hass