#!/usr/bin/env python3
"""
Генератор звуков для Beward DS07P-LP
Формат: G.711A (A-law), 8000 Гц, моно
"""

import wave
import numpy as np
import struct
import os
import requests
from requests.auth import HTTPDigestAuth
import base64
import time

# Параметры аудио для Beward
SAMPLE_RATE = 8000  # 8 кГц
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16 бит

def generate_sine_wave(freq_hz, duration_sec, volume=0.5):
    """Генерирует синусоиду заданной частоты"""
    t = np.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), endpoint=False)
    samples = (volume * 32767 * np.sin(2 * np.pi * freq_hz * t)).astype(np.int16)
    return samples

def generate_beep():
    """Короткий звук "бип" (0.2 сек, 1000 Гц)"""
    return generate_sine_wave(1000, 0.2, 0.3)

def generate_ding():
    """Звук "дзынь" (0.3 сек, 1500 Гц с затуханием)"""
    t = np.linspace(0, 0.3, int(SAMPLE_RATE * 0.3), endpoint=False)
    # Затухающая синусоида
    envelope = np.exp(-t * 10)  # экспоненциальное затухание
    samples = (0.4 * 32767 * envelope * np.sin(2 * np.pi * 1500 * t)).astype(np.int16)
    return samples

def generate_ringtone():
    """Рингтон (3 коротких звука)"""
    part1 = generate_sine_wave(600, 0.15, 0.3)
    part2 = generate_sine_wave(800, 0.15, 0.3)
    part3 = generate_sine_wave(1000, 0.15, 0.3)
    silence = np.zeros(int(SAMPLE_RATE * 0.1), dtype=np.int16)
    
    # Склеиваем
    ringtone = np.concatenate([part1, silence, part2, silence, part3, silence])
    return ringtone

def generate_notification():
    """Звук уведомления (двойной сигнал)"""
    beep1 = generate_sine_wave(800, 0.1, 0.4)
    beep2 = generate_sine_wave(1200, 0.1, 0.4)
    silence = np.zeros(int(SAMPLE_RATE * 0.05), dtype=np.int16)
    
    notification = np.concatenate([beep1, silence, beep2])
    return notification

def save_wav(filename, samples):
    """Сохраняет в WAV файл"""
    with wave.open(filename, 'wb') as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())
    print(f"✅ Saved {filename}")

def alaw_encode(sample):
    """Преобразование 16-bit PCM в 8-bit A-law (G.711A)"""
    # Простая реализация A-law
    sample = max(-32768, min(32767, sample))
    
    sign = (sample >> 8) & 0x80
    if sample < 0:
        sample = -sample
    
    if sample > 32635:
        sample = 32635
    
    if sample >= 256:
        exponent = 0
        while sample > 1:
            sample >>= 1
            exponent += 1
        exponent -= 1
        mantissa = (sample - 64) >> 2
    else:
        exponent = 0
        mantissa = sample >> 4
    
    alaw = (sign | (exponent << 4) | mantissa) ^ 0xD5
    return alaw & 0xFF

def convert_to_alaw(wav_filename, alaw_filename):
    """Конвертирует WAV в G.711A (A-law)"""
    with wave.open(wav_filename, 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
        
    # Преобразуем байты в 16-bit сэмплы
    samples = struct.unpack('<' + 'h' * (len(frames) // 2), frames)
    
    # Кодируем в A-law
    alaw_bytes = bytes([alaw_encode(s) for s in samples])
    
    # Сохраняем
    with open(alaw_filename, 'wb') as f:
        f.write(alaw_bytes)
    
    print(f"✅ Converted {wav_filename} -> {alaw_filename} ({len(alaw_bytes)} bytes)")

def send_to_beward(host, username, password, alaw_filename):
    """Отправляет звук на Beward через /cgi-bin/audio/transmit.cgi"""
    url = f"http://{host}/cgi-bin/audio/transmit.cgi"
    
    # Читаем A-law файл
    with open(alaw_filename, 'rb') as f:
        audio_data = f.read()
    
    # Создаем базовую аутентификацию
    auth_str = f"{username}:{password}"
    auth_base64 = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Content-Type": "audio/G.711A",
        "Content-Length": str(len(audio_data)),
        "Connection": "Keep-Alive",
        "Cache-Control": "no-cache",
        "Authorization": f"Basic {auth_base64}"
    }
    
    print(f"📤 Sending {alaw_filename} to {url}")
    print(f"   Size: {len(audio_data)} bytes")
    print(f"   Duration: {len(audio_data) / 8000:.2f} seconds")
    
    try:
        response = requests.post(url, headers=headers, data=audio_data, timeout=5)
        if response.status_code == 200:
            print("✅ Sound sent successfully!")
            return True
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return False

def main():
    """Главная функция"""
    print("=" * 50)
    print("🎵 Beward Sound Generator for DS07P-LP")
    print("=" * 50)
    
    # Создаем папку для звуков
    os.makedirs("beward_sounds", exist_ok=True)
    
    # Генерируем звуки
    print("\n🎵 Generating sounds...")
    
    sounds = {
        "beep": generate_beep,
        "ding": generate_ding,
        "ringtone": generate_ringtone,
        "notification": generate_notification
    }
    
    wav_files = []
    for name, generator in sounds.items():
        wav_filename = f"beward_sounds/{name}.wav"
        samples = generator()
        save_wav(wav_filename, samples)
        wav_files.append((name, wav_filename))
    
    # Конвертируем в A-law
    print("\n🔄 Converting to G.711A (A-law)...")
    alaw_files = []
    for name, wav_file in wav_files:
        alaw_file = f"beward_sounds/{name}.alaw"
        convert_to_alaw(wav_file, alaw_file)
        alaw_files.append((name, alaw_file))
    
    print("\n📋 Generated files:")
    for name, alaw_file in alaw_files:
        size = os.path.getsize(alaw_file)
        duration = size / 8000
        print(f"   - {name}.alaw: {size} bytes ({duration:.2f} sec)")
    
    # Спрашиваем, хочет ли пользователь отправить на устройство
    print("\n" + "=" * 50)
    send_now = input("📡 Send sounds to Beward device now? (y/n): ").lower()
    
    if send_now == 'y':
        host = input("Enter Beward IP address: ")
        username = input("Username (default: admin): ") or "admin"
        password = input("Password: ")
        
        print("\n📡 Sending sounds to device...")
        for name, alaw_file in alaw_files:
            print(f"\n--- Testing {name} ---")
            send_to_beward(host, username, password, alaw_file)
            time.sleep(1)  # Пауза между звуками
    
    print("\n✅ Done! Files are in 'beward_sounds' directory")
    print("\nTo use these files in Home Assistant:")
    print("1. Copy them to your HA config directory")
    print("2. Use in automations with shell_command or REST command")

if __name__ == "__main__":
    main()