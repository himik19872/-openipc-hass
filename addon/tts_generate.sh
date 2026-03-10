#!/bin/bash
# Скрипт для генерации A-law (G.711A) для Beward камер
# Используется внутри аддона

MESSAGE="$1"
LANG="${2:-ru}"
FILENAME="$3"

if [ -z "$MESSAGE" ] || [ -z "$FILENAME" ]; then
    echo "Usage: $0 <text> <language> <output_file.alaw>"
    exit 1
fi

TIMESTAMP=$(date +%s)
TEMP_MP3="/tmp/tts_${TIMESTAMP}.mp3"

# Генерируем TTS через gTTS
python3 -c "
import sys
try:
    from gtts import gTTS
    tts = gTTS(text='''$MESSAGE''', lang='$LANG', slow=False)
    tts.save('$TEMP_MP3')
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" || exit 1

# Конвертируем в A-law (G.711A) 8000Hz, mono
ffmpeg -y -i "$TEMP_MP3" -ar 8000 -ac 1 -f alaw "$FILENAME" 2>/dev/null || exit 1

# Удаляем временный файл
rm -f "$TEMP_MP3"

echo "✅ A-law файл создан: $FILENAME"
exit 0