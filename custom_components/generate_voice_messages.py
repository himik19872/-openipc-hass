#!/usr/bin/env python3
"""
Генератор простых голосовых сообщений для Beward
Использует очень простые тона, имитирующие голос
"""

import wave
import struct
import os
import math

SAMPLE_RATE = 8000
CHANNELS = 1
SAMPLE_WIDTH = 2

def generate_word(notes, duration_per_note=0.15, volume=0.6):
    """Генерирует последовательность тонов (имитация слова)"""
    samples = []
    for freq in notes:
        # Генерируем тон
        for i in range(int(SAMPLE_RATE * duration_per_note)):
            t = i / SAMPLE_RATE
            # Добавляем небольшую модуляцию для естественности
            mod_freq = freq + 20 * math.sin(2 * math.pi * 5 * t)
            sample = int(volume * 32767 * math.sin(2 * math.pi * mod_freq * t))
            samples.append(sample)
        # Короткая пауза между "буквами"
        samples.extend([0] * int(SAMPLE_RATE * 0.02))
    return samples

def generate_welcome():
    """'Добро пожаловать' - последовательность тонов"""
    # Имитация слова "добро" (низкие тона)
    word1 = generate_word([400, 500, 600, 500], 0.15, 0.6)
    # Пауза
    word1.extend([0] * int(SAMPLE_RATE * 0.1))
    # Имитация слова "пожаловать" (средние тона)
    word2 = generate_word([600, 700, 800, 700, 600], 0.15, 0.6)
    return word1 + word2

def generate_door_open():
    """'Дверь открыта' - последовательность тонов"""
    # "дверь"
    part1 = generate_word([500, 600, 500, 400], 0.12, 0.6)
    part1.extend([0] * int(SAMPLE_RATE * 0.08))
    # "открыта"
    part2 = generate_word([600, 700, 800, 700, 600], 0.12, 0.6)
    return part1 + part2

def generate_door_closed():
    """'Дверь закрыта' - последовательность тонов"""
    # "дверь"
    part1 = generate_word([500, 600, 500, 400], 0.12, 0.6)
    part1.extend([0] * int(SAMPLE_RATE * 0.08))
    # "закрыта"
    part2 = generate_word([400, 300, 400, 300, 200], 0.12, 0.6)
    return part1 + part2

def generate_motion():
    """'Обнаружено движение' - последовательность"""
    part1 = generate_word([600, 700, 800, 700], 0.1, 0.6)
    part1.extend([0] * int(SAMPLE_RATE * 0.08))
    part2 = generate_word([500, 600, 700, 600, 500], 0.1, 0.6)
    return part1 + part2

def generate_alert():
    """'Внимание тревога' - резкие тона"""
    part1 = generate_word([800, 800, 800], 0.1, 0.7)
    part1.extend([0] * int(SAMPLE_RATE * 0.05))
    part2 = generate_word([600, 700, 800, 900], 0.1, 0.7)
    return part1 + part2

def generate_success():
    """'Успешно' - восходящий звук"""
    return generate_word([500, 600, 700, 800], 0.15, 0.6)

def generate_error():
    """'Ошибка' - нисходящий звук"""
    return generate_word([800, 700, 600, 500], 0.15, 0.6)

def generate_hello():
    """'Здравствуйте' - приветствие"""
    return generate_word([500, 600, 700, 800, 700, 600], 0.12, 0.6)

def generate_goodbye():
    """'До свидания' - прощание"""
    part1 = generate_word([600, 500, 400], 0.15, 0.6)
    part1.extend([0] * int(SAMPLE_RATE * 0.05))
    part2 = generate_word([400, 300, 200, 100], 0.15, 0.6)
    return part1 + part2

def save_wav(filename, samples):
    """Сохраняет WAV файл"""
    with wave.open(filename, 'wb') as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        
        frames = b''
        for sample in samples:
            frames += struct.pack('<h', sample)
        wav.writeframes(frames)
    print(f"✅ Saved {filename}")

def alaw_encode(sample):
    """A-law encoding"""
    sample = max(-32768, min(32767, sample))
    
    sign = (sample >> 8) & 0x80
    if sample < 0:
        sample = -sample
    
    if sample > 32635:
        sample = 32635
    
    if sample >= 256:
        exponent = 0
        temp = sample
        while temp > 1:
            temp >>= 1
            exponent += 1
        exponent -= 1
        mantissa = (sample - 64) >> 2
    else:
        exponent = 0
        mantissa = sample >> 4
    
    alaw = (sign | (exponent << 4) | mantissa) ^ 0xD5
    return alaw & 0xFF

def wav_to_alaw(wav_file, alaw_file):
    """Конвертирует WAV в A-law"""
    with wave.open(wav_file, 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
    
    sample_count = len(frames) // 2
    samples = struct.unpack('<' + 'h' * sample_count, frames)
    alaw_bytes = bytes([alaw_encode(s) for s in samples])
    
    with open(alaw_file, 'wb') as f:
        f.write(alaw_bytes)
    
    size = len(alaw_bytes)
    print(f"✅ Converted {alaw_file} ({size} bytes, {size/8000:.2f} sec)")

def main():
    print("=" * 60)
    print("🗣️ Beward Voice Messages Generator")
    print("=" * 60)
    
    # Создаем папку
    os.makedirs("/config/beward_voices", exist_ok=True)
    
    # Генерируем голосовые сообщения
    voices = {
        "welcome": generate_welcome,        # Добро пожаловать
        "door_open": generate_door_open,    # Дверь открыта
        "door_closed": generate_door_closed, # Дверь закрыта
        "motion": generate_motion,          # Обнаружено движение
        "alert": generate_alert,            # Внимание тревога
        "success": generate_success,        # Успешно
        "error": generate_error,            # Ошибка
        "hello": generate_hello,            # Здравствуйте
        "goodbye": generate_goodbye,        # До свидания
    }
    
    for name, func in voices.items():
        print(f"\n🔊 Generating {name}...")
        samples = func()
        wav_file = f"/config/beward_voices/{name}.wav"
        save_wav(wav_file, samples)
        
        alaw_file = f"/config/beward_voices/{name}.alaw"
        wav_to_alaw(wav_file, alaw_file)
        
        # Удаляем WAV файл
        os.remove(wav_file)
    
    print("\n" + "=" * 60)
    print("📋 Generated voice files in /config/beward_voices/:")
    for name in voices.keys():
        alaw_file = f"/config/beward_voices/{name}.alaw"
        if os.path.exists(alaw_file):
            size = os.path.getsize(alaw_file)
            print(f"  • {name}.alaw: {size} bytes ({size/8000:.2f} sec)")
    
    print("\n✅ Done! Copy to HA if needed:")
    print("cp /config/beward_voices/*.alaw /config/beward_voices/")

if __name__ == "__main__":
    main()