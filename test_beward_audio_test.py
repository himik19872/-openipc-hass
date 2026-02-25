#!/usr/bin/env python3
"""
Тестер аудио для Beward DS07P-LP
"""

import asyncio
import aiohttp
import base64
import sys
import os

async def test_audio(host, username, password, audio_file):
    """Тестирует отправку аудио с разными параметрами"""
    
    print("=" * 60)
    print(f"Testing audio file: {audio_file}")
    print("=" * 60)
    
    # Читаем файл
    with open(audio_file, 'rb') as f:
        audio_data = f.read()
    
    file_size = len(audio_data)
    file_size_mb = file_size / 1024 / 1024
    duration = file_size / 8000  # для G.711A
    
    print(f"File size: {file_size} bytes ({file_size_mb:.2f} MB)")
    print(f"Duration: {duration:.2f} seconds")
    
    # Пробуем разные методы
    methods = [
        {
            "name": "Standard POST with audio/G.711A",
            "url": f"http://{host}/cgi-bin/audio/transmit.cgi",
            "headers": {
                "Content-Type": "audio/G.711A",
                "Content-Length": str(file_size),
                "Connection": "Keep-Alive",
                "Cache-Control": "no-cache",
            }
        },
        {
            "name": "Standard POST with audio/basic",
            "url": f"http://{host}/cgi-bin/audio/transmit.cgi",
            "headers": {
                "Content-Type": "audio/basic",
                "Content-Length": str(file_size),
                "Connection": "Keep-Alive",
                "Cache-Control": "no-cache",
            }
        },
        {
            "name": "Alternative endpoint",
            "url": f"http://{host}/cgi-bin/transmitaudio_cgi",
            "headers": {
                "Content-Type": "G.711A;boundary=audio",
                "Content-Length": str(file_size),
                "Connection": "Keep-Alive",
                "Cache-Control": "no-cache",
            }
        }
    ]
    
    auth_str = f"{username}:{password}"
    auth_base64 = base64.b64encode(auth_str.encode()).decode()
    
    for method in methods:
        print(f"\n📡 Testing: {method['name']}")
        print(f"URL: {method['url']}")
        
        # Добавляем авторизацию
        method['headers']["Authorization"] = f"Basic {auth_base64}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(method['url'], 
                                      headers=method['headers'], 
                                      data=audio_data, 
                                      timeout=10) as response:
                    
                    print(f"Status: {response.status}")
                    if response.status == 200:
                        text = await response.text()
                        print(f"Response: {text}")
                        print("✅ SUCCESS!")
                    else:
                        text = await response.text()
                        print(f"Error: {text[:200]}")
                        print("❌ FAILED")
        except Exception as e:
            print(f"Exception: {e}")
            print("❌ FAILED")
        
        await asyncio.sleep(1)

async def main():
    if len(sys.argv) < 5:
        print("Usage: python test_beward_audio.py HOST USERNAME PASSWORD AUDIO_FILE")
        print("Example: python test_beward_audio.py 192.168.1.10 admin password beep.alaw")
        return
    
    host = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    audio_file = sys.argv[4]
    
    if not os.path.exists(audio_file):
        print(f"File not found: {audio_file}")
        return
    
    await test_audio(host, username, password, audio_file)

if __name__ == "__main__":
    asyncio.run(main())