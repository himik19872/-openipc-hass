#!/usr/bin/env python3
"""
Скачивание готовых звуков для Beward
"""

import os
import requests
import base64

# URL с готовыми звуками в формате G.711A
SOUNDS = {
    "beep": "https://raw.githubusercontent.com/Beward/audio-samples/main/beep.alaw",
    "ding": "https://raw.githubusercontent.com/Beward/audio-samples/main/ding.alaw",
    "ringtone": "https://raw.githubusercontent.com/Beward/audio-samples/main/ringtone.alaw",
    "notification": "https://raw.githubusercontent.com/Beward/audio-samples/main/notification.alaw",
    "doorbell": "https://raw.githubusercontent.com/Beward/audio-samples/main/doorbell.alaw",
}

def download_sounds():
    """Скачивает готовые звуки"""
    print("=" * 50)
    print("📥 Downloading Beward sounds")
    print("=" * 50)
    
    # Создаем папку
    os.makedirs("beward_sounds", exist_ok=True)
    
    for name, url in SOUNDS.items():
        print(f"\n📥 Downloading {name}...")
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                filename = f"beward_sounds/{name}.alaw"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                
                size = len(response.content)
                duration = size / 8000
                print(f"   ✅ Saved: {filename}")
                print(f"   📊 Size: {size} bytes ({duration:.2f} sec)")
            else:
                print(f"   ❌ Failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Download complete!")
    print("\nFiles saved in 'beward_sounds' directory")
    print("\nTo test:")
    print("1. Copy to Home Assistant config directory")
    print("2. Use in automations or services")

def send_to_beward(host, username, password, alaw_file):
    """Отправляет звук на Beward"""
    url = f"http://{host}/cgi-bin/audio/transmit.cgi"
    
    with open(alaw_file, 'rb') as f:
        audio_data = f.read()
    
    auth_str = f"{username}:{password}"
    auth_base64 = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Content-Type": "audio/G.711A",
        "Content-Length": str(len(audio_data)),
        "Connection": "Keep-Alive",
        "Cache-Control": "no-cache",
        "Authorization": f"Basic {auth_base64}"
    }
    
    print(f"📤 Sending {os.path.basename(alaw_file)}...")
    try:
        response = requests.post(url, headers=headers, data=audio_data, timeout=5)
        if response.status_code == 200:
            print("   ✅ Success!")
            return True
        else:
            print(f"   ❌ Failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--send":
        # Режим отправки
        if len(sys.argv) < 5:
            print("Usage: python download_beward_sounds.py --send HOST USERNAME PASSWORD")
            sys.exit(1)
        
        host = sys.argv[2]
        username = sys.argv[3]
        password = sys.argv[4]
        
        # Сначала скачиваем, если нет
        if not os.path.exists("beward_sounds"):
            download_sounds()
        
        # Отправляем все звуки
        for sound in SOUNDS.keys():
            alaw_file = f"beward_sounds/{sound}.alaw"
            if os.path.exists(alaw_file):
                send_to_beward(host, username, password, alaw_file)
    else:
        # Просто скачиваем
        download_sounds()