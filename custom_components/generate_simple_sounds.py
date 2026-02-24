#!/usr/bin/env python3
"""
Простой генератор звуков для Beward
"""

import wave
import struct
import os
import base64
import math
import sys
import time
import requests  # Импорт в начале файла

# Параметры аудио
SAMPLE_RATE = 8000
CHANNELS = 1
SAMPLE_WIDTH = 2

def generate_sine(freq, duration, volume=0.5):
    """Генерирует синусоиду"""
    samples = []
    samples_count = int(SAMPLE_RATE * duration)
    for i in range(samples_count):
        t = i / SAMPLE_RATE
        sample = int(volume * 32767 * math.sin(2 * math.pi * freq * t))
        samples.append(sample)
    return samples

def generate_beep():
    """Короткий бип"""
    return generate_sine(1000, 0.2, 0.3)

def generate_ding():
    """Звук с затуханием"""
    samples = []
    samples_count = int(SAMPLE_RATE * 0.3)
    for i in range(samples_count):
        t = i / SAMPLE_RATE
        envelope = math.exp(-t * 10)
        sample = int(0.4 * 32767 * envelope * math.sin(2 * math.pi * 1500 * t))
        samples.append(sample)
    return samples

def generate_ringtone():
    """Рингтон"""
    samples = []
    samples.extend(generate_sine(600, 0.15, 0.3))
    samples.extend([0] * int(SAMPLE_RATE * 0.1))
    samples.extend(generate_sine(800, 0.15, 0.3))
    samples.extend([0] * int(SAMPLE_RATE * 0.1))
    samples.extend(generate_sine(1000, 0.15, 0.3))
    return samples

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

def wav_to_alaw(wav_filename, alaw_filename):
    """Конвертирует WAV в A-law"""
    with wave.open(wav_filename, 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
    
    sample_count = len(frames) // 2
    samples = struct.unpack('<' + 'h' * sample_count, frames)
    
    alaw_bytes = bytes([alaw_encode(s) for s in samples])
    
    with open(alaw_filename, 'wb') as f:
        f.write(alaw_bytes)
    
    print(f"✅ Converted {alaw_filename} ({len(alaw_bytes)} bytes)")

def send_to_beward(host, username, password, alaw_file):
    """Отправляет звук на Beward"""
    url = f"http://{host}/cgi-bin/audio/transmit.cgi"
    
    try:
        with open(alaw_file, 'rb') as f:
            audio_data = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {alaw_file}")
        return False
    
    auth = base64.b64encode(f"{username}:{password}".encode()).decode()
    
    headers = {
        "Content-Type": "audio/G.711A",
        "Content-Length": str(len(audio_data)),
        "Connection": "Keep-Alive",
        "Cache-Control": "no-cache",
        "Authorization": f"Basic {auth}"
    }
    
    print(f"\n📤 Testing {os.path.basename(alaw_file)}")
    print(f"Size: {len(audio_data)} bytes ({len(audio_data)/8000:.2f} sec)")
    print(f"URL: {url}")
    
    try:
        response = requests.post(url, headers=headers, data=audio_data, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print(f"Response: {response.text}")
            print("✅ SUCCESS!")
            return True
        else:
            print(f"❌ Error: {response.text[:200]}")
            return False
    except requests.exceptions.Timeout:
        print("❌ Timeout error")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - camera not reachable")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("=" * 60)
    print("🎵 Beward Sound Generator")
    print("=" * 60)
    
    # Проверяем установку requests
    print(f"📚 Requests version: {requests.__version__}")
    
    # Создаем папку
    os.makedirs("beward_sounds", exist_ok=True)
    
    # Генерируем звуки
    sounds = {
        "beep": generate_beep,
        "ding": generate_ding,
        "ringtone": generate_ringtone,
    }
    
    for name, func in sounds.items():
        print(f"\n🔊 Generating {name}...")
        samples = func()
        wav_file = f"beward_sounds/{name}.wav"
        save_wav(wav_file, samples)
        
        alaw_file = f"beward_sounds/{name}.alaw"
        wav_to_alaw(wav_file, alaw_file)
    
    print("\n📋 Generated files:")
    for name in sounds.keys():
        alaw_file = f"beward_sounds/{name}.alaw"
        size = os.path.getsize(alaw_file)
        print(f"  • {name}.alaw: {size} bytes ({size/8000:.2f} sec)")
    
    print("\n" + "=" * 60)
    test = input("📡 Test sounds on Beward? (y/n): ").lower()
    
    if test == 'y':
        host = "192.168.1.10"
        username = "admin"
        password = input("🔑 Password for Beward: ")
        
        # Проверяем доступность камеры сначала
        print(f"\n🔍 Testing connection to {host}...")
        try:
            test_response = requests.get(f"http://{host}/cgi-bin/systeminfo_cgi?action=get", 
                                       auth=(username, password), timeout=3)
            if test_response.status_code == 200:
                print("✅ Camera is reachable")
            else:
                print(f"⚠️ Camera returned status {test_response.status_code}")
        except Exception as e:
            print(f"❌ Cannot reach camera: {e}")
            return
        
        for name in sounds.keys():
            alaw_file = f"beward_sounds/{name}.alaw"
            send_to_beward(host, username, password, alaw_file)
            time.sleep(1)
    
    print("\n✅ Done!")

if __name__ == "__main__":
    main()