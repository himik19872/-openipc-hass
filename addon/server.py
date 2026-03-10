#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template, send_from_directory
import subprocess
import json
import os
import logging
import tempfile
import base64
from datetime import datetime
import requests
import re
import time
import threading
import yaml
import glob
import shutil
from typing import Dict, Optional, List

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL для доступа к Home Assistant через Supervisor
HASS_URL = os.environ.get('HASS_URL', 'http://supervisor/core')
SUPERVISOR_TOKEN = os.environ.get('SUPERVISOR_TOKEN', '')
HASS_TOKEN = os.environ.get('HASSIO_TOKEN', SUPERVISOR_TOKEN)

# Пути к скриптам генерации TTS
TTS_GENERATE_SCRIPT = "/app/tts_generate_openipc.sh"
TTS_GENERATE_BEWARD_SCRIPT = "/app/tts_generate.sh"

# Файлы конфигурации
QR_DEBUG_FILE = "/config/qr_debug.log"
CONFIG_FILE = "/config/openipc_bridge_config.yaml"
TRANSLATIONS_DIR = "/app/translations"

# Хранилище для заданий сканирования
scan_jobs: Dict[str, dict] = {}

# Статистика QR
qr_stats = {
    "total_requests": 0,
    "successful_scans": 0,
    "failed_scans": 0,
    "total_codes_found": 0,
    "by_camera": {},
    "by_type": {},
    "last_scan_time": None,
    "last_code": None
}

state = {
    "started_at": datetime.now().isoformat(),
    "requests": 0
}

# Счетчик для отладочных снимков
debug_counter = 0

# Конфигурация по умолчанию
DEFAULT_CONFIG = {
    "cameras": [
        {
            "name": "OpenIPC SIP",
            "ip": "192.168.1.4",
            "type": "openipc",
            "username": "root",
            "password": "12345",
            "snapshot_endpoints": ["/image.jpg", "/cgi-bin/api.cgi?cmd=Snap&channel=0"],
            "tts_endpoint": "/play_audio",
            "tts_format": "pcm",
            "relay_endpoints": {
                "relay1_on": "",
                "relay1_off": "",
                "relay2_on": "",
                "relay2_off": ""
            }
        },
        {
            "name": "Beward Doorbell",
            "ip": "192.168.1.10",
            "type": "beward",
            "username": "admin",
            "password": "Q96811621w",
            "snapshot_endpoints": ["/cgi-bin/jpg/image.cgi", "/cgi-bin/snapshot.cgi"],
            "tts_endpoint": "/cgi-bin/audio/transmit.cgi",
            "tts_format": "alaw",
            "relay_endpoints": {
                "relay1_on": "/cgi-bin/alarmout_cgi?action=set&Output=0&Status=1",
                "relay1_off": "/cgi-bin/alarmout_cgi?action=set&Output=0&Status=0",
                "relay2_on": "/cgi-bin/alarmout_cgi?action=set&Output=1&Status=1",
                "relay2_off": "/cgi-bin/alarmout_cgi?action=set&Output=1&Status=0"
            }
        }
    ],
    "tts": {
        "provider": "google",
        "google": {
            "language": "ru",
            "slow": False
        },
        "rhvoice": {
            "voice": "anna",
            "language": "ru",
            "speed": 1.0
        }
    },
    "logging": {
        "level": "INFO",
        "debug_qr": True,
        "max_debug_images": 100
    }
}

# Загружаем конфигурацию
config = DEFAULT_CONFIG.copy()

def load_config():
    """Загрузить конфигурацию из файла"""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    # Рекурсивно обновляем конфигурацию
                    config = deep_merge(config, file_config)
                    
                    # Настраиваем уровень логирования
                    level = config['logging'].get('level', 'INFO')
                    logger.setLevel(getattr(logging, level))
                    
                    logger.info(f"✅ Configuration loaded from {CONFIG_FILE}")
                    logger.info(f"   Cameras: {len(config['cameras'])}")
                    logger.info(f"   TTS Provider: {config['tts']['provider']}")
        else:
            # Создаем файл с конфигурацией по умолчанию
            save_default_config()
            logger.info(f"✅ Created default configuration at {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")

def deep_merge(base, update):
    """Рекурсивное слияние словарей"""
    for key, value in update.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def save_default_config():
    """Сохранить конфигурацию по умолчанию"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    except Exception as e:
        logger.error(f"❌ Failed to save default config: {e}")

def get_camera_config(camera_ip: str) -> Optional[Dict]:
    """Получить конфигурацию камеры по IP"""
    for cam in config['cameras']:
        if cam['ip'] == camera_ip:
            return cam
    return None

def get_camera_config_by_name(camera_name: str) -> Optional[Dict]:
    """Получить конфигурацию камеры по имени"""
    for cam in config['cameras']:
        if cam['name'] == camera_name:
            return cam
    return None

def write_qr_debug(msg):
    """Запись в отладочный файл QR"""
    if not config['logging'].get('debug_qr', True):
        return
    try:
        with open(QR_DEBUG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now()}: {msg}\n")
    except:
        pass

def load_translations(lang='en'):
    """Загрузить переводы"""
    try:
        trans_file = os.path.join(TRANSLATIONS_DIR, f"{lang}.yaml")
        if os.path.exists(trans_file):
            with open(trans_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load translations: {e}")
    return {}

@app.route('/')
def index():
    return jsonify({
        "service": "OpenIPC Bridge",
        "status": "running",
        "started_at": state["started_at"],
        "requests": state["requests"],
        "qr_stats": qr_stats,
        "active_scans": len(scan_jobs),
        "config": {
            "cameras_count": len(config['cameras']),
            "tts_provider": config['tts']['provider']
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/config')
def config_page():
    """Страница конфигурации"""
    return render_template('config.html')

@app.route('/api/config', methods=['GET'])
def get_config_api():
    """Получить текущую конфигурацию"""
    return jsonify({
        "success": True,
        "config": config
    })

@app.route('/api/config/save', methods=['POST'])
def save_config():
    """Сохранить конфигурацию"""
    try:
        new_config = request.json
        
        # Создаем резервную копию
        if os.path.exists(CONFIG_FILE):
            backup_file = f"{CONFIG_FILE}.backup"
            shutil.copy2(CONFIG_FILE, backup_file)
        
        # Сохраняем новую конфигурацию
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        # Перезагружаем конфигурацию
        global config
        config = new_config
        
        # Настраиваем логирование
        level = config['logging'].get('level', 'INFO')
        logger.setLevel(getattr(logging, level))
        
        logger.info("✅ Configuration saved successfully")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"❌ Failed to save config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/config/reload', methods=['POST'])
def reload_config_api():
    """Перезагрузить конфигурацию"""
    try:
        load_config()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/debug/clear', methods=['POST'])
def clear_debug():
    """Очистить отладочные снимки"""
    try:
        debug_files = glob.glob("/config/www/qr_debug_*.jpg")
        marked_files = glob.glob("/config/www/qr_marked_*.jpg")
        
        for f in debug_files + marked_files:
            try:
                os.remove(f)
            except:
                pass
        
        logger.info(f"✅ Cleared {len(debug_files) + len(marked_files)} debug images")
        return jsonify({"success": True, "count": len(debug_files) + len(marked_files)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/qr/stats')
def qr_statistics():
    """Получить статистику QR сканирования"""
    return jsonify({
        "success": True,
        "stats": qr_stats
    })

@app.route('/api/qr/debug')
def qr_debug():
    """Получить последние 50 строк отладки QR"""
    try:
        if os.path.exists(QR_DEBUG_FILE):
            with open(QR_DEBUG_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-50:]
            return jsonify({
                "success": True,
                "debug": lines
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": True, "debug": []})

@app.route('/api/translations/<lang>')
def get_translations(lang):
    """Получить переводы для указанного языка"""
    return jsonify(load_translations(lang))

def capture_snapshot_from_camera(camera_ip: str) -> Optional[bytes]:
    """Получить снимок с камеры используя конфигурацию"""
    global debug_counter
    
    try:
        # Получаем конфигурацию камеры
        cam_config = get_camera_config(camera_ip)
        if not cam_config:
            logger.error(f"❌ No configuration found for camera {camera_ip}")
            return None
        
        camera_type = cam_config.get('type', 'openipc')
        username = cam_config.get('username', 'root')
        password = cam_config.get('password', '12345')
        endpoints = cam_config.get('snapshot_endpoints', ['/image.jpg'])
        
        auth = (username, password)
        
        for endpoint in endpoints:
            url = f"http://{camera_ip}{endpoint}"
            logger.info(f"📸 Capturing {camera_type} snapshot from {url}")
            
            try:
                response = requests.get(url, timeout=5, auth=auth)
                if response.status_code == 200:
                    data = response.content
                    if len(data) > 1000:
                        logger.info(f"✅ Snapshot captured: {len(data)} bytes from {endpoint}")
                        
                        # Сохраняем отладочные снимки
                        if config['logging'].get('debug_qr', True):
                            debug_counter += 1
                            max_debug = config['logging'].get('max_debug_images', 100)
                            
                            if debug_counter <= max_debug and debug_counter % 3 == 0:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                debug_path = f"/config/www/qr_debug_{camera_type}_{timestamp}.jpg"
                                try:
                                    with open(debug_path, 'wb') as f:
                                        f.write(data)
                                    logger.info(f"💾 Debug snapshot saved: {debug_path}")
                                    capture_snapshot_from_camera.last_debug_path = debug_path
                                except Exception as e:
                                    logger.error(f"Failed to save debug snapshot: {e}")
                        
                        return data
                    else:
                        logger.warning(f"Snapshot too small: {len(data)} bytes from {endpoint}")
                else:
                    logger.warning(f"HTTP {response.status_code} from {endpoint}")
            except Exception as e:
                logger.debug(f"Failed to connect to {endpoint}: {e}")
                continue
        
        logger.warning(f"❌ All snapshot attempts failed for {camera_ip}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to capture snapshot: {e}")
        return None

def get_camera_entity_id(camera_ip: str) -> str:
    """Получить entity_id камеры по IP"""
    cam_config = get_camera_config(camera_ip)
    if cam_config:
        name = cam_config.get('name', '').lower().replace(' ', '_')
        return f"camera.{name}"
    return f"camera.openipc_{camera_ip.replace('.', '_')}"

def scan_qr_from_image(image_bytes: bytes) -> Optional[Dict]:
    """Сканировать QR код на изображении"""
    try:
        import cv2
        import numpy as np
        from pyzbar.pyzbar import decode
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            logger.error("Failed to decode image")
            return None
        
        height, width = img.shape[:2]
        logger.debug(f"Image size: {width}x{height}")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        barcodes = decode(gray)
        
        if barcodes:
            barcode = barcodes[0]
            qr_data = barcode.data.decode('utf-8')
            qr_type = barcode.type
            
            logger.info(f"✅ QR Code found: {qr_data}")
            
            # Рисуем прямоугольник на отладочном снимке
            if hasattr(capture_snapshot_from_camera, "last_debug_path"):
                try:
                    points = barcode.polygon
                    if len(points) == 4:
                        pts = np.array([(p.x, p.y) for p in points], np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(img, [pts], True, (0, 255, 0), 3)
                        
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        marked_path = f"/config/www/qr_marked_{timestamp}.jpg"
                        cv2.imwrite(marked_path, img)
                        logger.info(f"💾 Marked image saved: {marked_path}")
                except Exception as e:
                    logger.error(f"Failed to draw rectangle: {e}")
            
            return {
                "data": qr_data,
                "type": qr_type,
                "rect": {
                    "left": barcode.rect.left,
                    "top": barcode.rect.top,
                    "width": barcode.rect.width,
                    "height": barcode.rect.height
                }
            }
        else:
            logger.debug("No QR codes found in image")
            return None
            
    except Exception as e:
        logger.error(f"QR scan error: {e}")
        return None

def send_event_to_ha(event_type: str, event_data: dict):
    """Отправить событие в Home Assistant"""
    try:
        headers = {
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        }
        
        url = f"{HASS_URL}/api/events/{event_type}"
        logger.info(f"📤 Sending event {event_type} to HA")
        
        response = requests.post(url, headers=headers, json=event_data, timeout=2)
        
        if response.status_code == 200:
            logger.info(f"✅ Event {event_type} sent to HA")
        else:
            logger.warning(f"Failed to send event: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending event: {e}")

def continuous_scan(scan_id: str, camera_id: str, expected_code: str, timeout: int):
    """Непрерывное сканирование QR в фоновом потоке"""
    logger.info(f"🔄 Starting continuous scan {scan_id} for {camera_id}")
    
    start_time = time.time()
    scan_count = 0
    failed_attempts = 0
    
    while time.time() - start_time < timeout:
        scan_count += 1
        elapsed = int(time.time() - start_time)
        remaining = timeout - elapsed
        
        logger.info(f"📸 Scan #{scan_count} - {remaining}s remaining")
        
        try:
            # Получаем снимок с камеры
            snapshot = capture_snapshot_from_camera(camera_id)
            
            if snapshot:
                failed_attempts = 0
                # Сканируем QR
                qr_result = scan_qr_from_image(snapshot)
                
                if qr_result:
                    qr_data = qr_result.get('data', '')
                    
                    logger.info(f"🎯🎯🎯 QR CODE DETECTED: {qr_data}")
                    write_qr_debug(f"🎯 QR CODE DETECTED: {qr_data}")
                    
                    # Отправляем событие в HA
                    event_data = {
                        "camera": get_camera_entity_id(camera_id),
                        "data": qr_data,
                        "type": qr_result.get('type', 'QRCODE'),
                        "scan_id": scan_id,
                        "expected_code": expected_code,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    send_event_to_ha("openipc_qr_detected", event_data)
                    
                    # Обновляем статус задания
                    scan_jobs[scan_id].update({
                        "status": "completed",
                        "end_time": time.time(),
                        "result": qr_result,
                        "scan_count": scan_count
                    })
                    
                    logger.info(f"✅ Scan {scan_id} completed - code detected")
                    return
                else:
                    logger.debug("No QR code in this frame")
            else:
                failed_attempts += 1
                logger.warning(f"Failed to capture snapshot (attempt {failed_attempts})")
                
                if failed_attempts > 5:
                    logger.error(f"Camera {camera_id} seems unavailable - too many failed attempts")
                    break
            
            # Обновляем статус
            scan_jobs[scan_id].update({
                "scan_count": scan_count,
                "last_scan": time.time(),
                "status": "running"
            })
            
        except Exception as e:
            logger.error(f"Error in scan {scan_id}: {e}")
            write_qr_debug(f"❌ Error in scan: {e}")
        
        time.sleep(2)
    
    # Таймаут
    camera_entity = get_camera_entity_id(camera_id)
    scan_jobs[scan_id].update({
        "status": "timeout",
        "end_time": time.time(),
        "result": None,
        "scan_count": scan_count
    })
    
    # Отправляем событие о таймауте
    event_data = {
        "camera": camera_entity,
        "scan_id": scan_id,
        "expected_code": expected_code,
        "timeout": timeout,
        "timestamp": datetime.now().isoformat()
    }
    send_event_to_ha("openipc_qr_timeout", event_data)
    
    logger.info(f"⏱️ Scan {scan_id} timed out after {timeout}s")
    write_qr_debug(f"⏱️ Scan timed out")

@app.route('/api/start_scan', methods=['POST'])
def start_scan():
    """Запуск непрерывного сканирования QR для камеры"""
    state["requests"] += 1
    data = request.json
    
    camera_id = data.get('camera_id')
    expected_code = data.get('expected_code', 'a4625vol')
    timeout = data.get('timeout', 300)
    
    # Проверяем, есть ли конфигурация для этой камеры
    cam_config = get_camera_config(camera_id)
    if not cam_config:
        logger.warning(f"⚠️ No configuration found for camera {camera_id}, using defaults")
    
    logger.info(f"🎯 Starting continuous scan for {camera_id}")
    logger.info(f"🎯 Expected code: {expected_code}")
    write_qr_debug(f"🎯 Starting continuous scan for {camera_id} with expected code: {expected_code}")
    
    scan_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    
    scan_jobs[scan_id] = {
        "scan_id": scan_id,
        "camera_id": camera_id,
        "expected_code": expected_code,
        "timeout": timeout,
        "start_time": time.time(),
        "status": "starting",
        "result": None,
        "scan_count": 0
    }
    
    thread = threading.Thread(
        target=continuous_scan,
        args=(scan_id, camera_id, expected_code, timeout)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "scan_id": scan_id,
        "message": f"Scan started for {camera_id}"
    })

@app.route('/api/scan_status/<scan_id>', methods=['GET'])
def scan_status(scan_id):
    """Получить статус сканирования"""
    state["requests"] += 1
    
    if scan_id in scan_jobs:
        return jsonify({
            "success": True,
            "scan": scan_jobs[scan_id]
        })
    
    return jsonify({
        "success": False,
        "error": "Scan not found"
    }), 404

@app.route('/api/stop_scan/<scan_id>', methods=['POST'])
def stop_scan(scan_id):
    """Остановить сканирование"""
    state["requests"] += 1
    
    if scan_id in scan_jobs:
        scan_jobs[scan_id].update({
            "status": "stopped",
            "end_time": time.time()
        })
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Scan not found"}), 404

@app.route('/api/barcode', methods=['POST'])
def barcode():
    """Распознавание штрих-кода с диагностикой"""
    state["requests"] += 1
    qr_stats["total_requests"] += 1
    
    data = request.json
    
    if not data:
        return jsonify({"success": False, "error": "No JSON data"}), 400
    
    image_data = data.get('image', '')
    camera_id = data.get('camera_id', 'unknown')
    
    if not image_data:
        qr_stats["failed_scans"] += 1
        return jsonify({"success": False, "error": "No image data"}), 400
    
    start_time = time.time()
    
    try:
        import cv2
        import numpy as np
        from pyzbar.pyzbar import decode
        
        # Декодируем изображение
        try:
            img_bytes = base64.b64decode(image_data)
            logger.info(f"Decoded {len(img_bytes)} bytes")
        except Exception as e:
            qr_stats["failed_scans"] += 1
            return jsonify({"success": False, "error": f"Base64 decode failed: {e}"}), 400
        
        # Декодируем через OpenCV
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            qr_stats["failed_scans"] += 1
            return jsonify({"success": False, "error": "Failed to decode image"}), 400
        
        # Конвертируем в grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Распознаем QR-коды
        barcodes = decode(gray)
        
        process_time = time.time() - start_time
        
        if barcodes:
            qr_stats["successful_scans"] += 1
            qr_stats["last_scan_time"] = datetime.now().isoformat()
            
            results = []
            for barcode in barcodes:
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                qr_stats["total_codes_found"] += 1
                qr_stats["by_type"][barcode_type] = qr_stats["by_type"].get(barcode_type, 0) + 1
                
                if camera_id not in qr_stats["by_camera"]:
                    qr_stats["by_camera"][camera_id] = {"scans": 0, "codes": 0}
                qr_stats["by_camera"][camera_id]["codes"] += 1
                
                qr_stats["last_code"] = barcode_data
                
                results.append({
                    "data": barcode_data,
                    "type": barcode_type,
                    "rect": {
                        "left": barcode.rect.left,
                        "top": barcode.rect.top,
                        "width": barcode.rect.width,
                        "height": barcode.rect.height
                    }
                })
            
            if camera_id not in qr_stats["by_camera"]:
                qr_stats["by_camera"][camera_id] = {"scans": 0, "codes": 0}
            qr_stats["by_camera"][camera_id]["scans"] += 1
            
            logger.info(f"✅ Found {len(results)} barcodes in {process_time:.2f}s")
            
            return jsonify({
                "success": True,
                "barcodes": results,
                "stats": {
                    "process_time_ms": int(process_time * 1000),
                    "codes_found": len(results)
                }
            })
        else:
            qr_stats["failed_scans"] += 1
            
            if camera_id not in qr_stats["by_camera"]:
                qr_stats["by_camera"][camera_id] = {"scans": 0, "codes": 0}
            qr_stats["by_camera"][camera_id]["scans"] += 1
            
            logger.debug(f"No barcodes found in {process_time:.2f}s")
            
            return jsonify({
                "success": True,
                "barcodes": [],
                "stats": {
                    "process_time_ms": int(process_time * 1000),
                    "codes_found": 0
                }
            })
        
    except Exception as e:
        qr_stats["failed_scans"] += 1
        logger.error(f"Barcode error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/camera/<path:camera_id>/barcode', methods=['POST'])
def camera_barcode(camera_id):
    """Endpoint для QR сканирования конкретной камеры"""
    logger.info(f"Camera barcode endpoint called for: {camera_id}")
    data = request.json or {}
    data['camera_id'] = camera_id
    return barcode()

# TTS endpoints
@app.route('/api/tts', methods=['POST'])
def tts():
    state["requests"] += 1
    data = request.json
    
    camera_id = data.get('camera_id')
    text = data.get('text', '')
    lang = data.get('lang', 'ru')
    
    logger.info(f"TTS request: camera={camera_id}, text={text}")
    
    if not camera_id or not text:
        return jsonify({"success": False, "error": "Missing camera_id or text"}), 400
    
    # Получаем конфигурацию камеры
    cam_config = get_camera_config(camera_id)
    if not cam_config:
        # Пробуем найти по имени
        cam_config = get_camera_config_by_name(camera_id)
    
    if cam_config:
        camera_ip = cam_config['ip']
        camera_type = cam_config['type']
        username = cam_config['username']
        password = cam_config['password']
        tts_format = cam_config.get('tts_format', 'pcm' if camera_type == 'openipc' else 'alaw')
        tts_endpoint = cam_config.get('tts_endpoint', '/cgi-bin/audio/transmit.cgi' if camera_type == 'beward' else '/play_audio')
    else:
        # Fallback на старую логику
        if camera_id == '192.168.1.10' or 'beward' in str(camera_id).lower():
            camera_type = 'beward'
            username = 'admin'
            password = 'Q96811621w'
            camera_ip = '192.168.1.10'
            tts_format = 'alaw'
            tts_endpoint = '/cgi-bin/audio/transmit.cgi'
        else:
            camera_type = 'openipc'
            username = 'root'
            password = '12345'
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', camera_id)
            camera_ip = ip_match.group(1) if ip_match else '192.168.1.4'
            tts_format = 'pcm'
            tts_endpoint = '/play_audio'
    
    camera_data = {
        "ip": camera_ip,
        "type": camera_type,
        "username": username,
        "password": password,
        "format": tts_format,
        "endpoint": tts_endpoint
    }
    
    if camera_type == 'beward' or tts_format == 'alaw':
        return _tts_for_beward(camera_data, text, lang)
    else:
        return _tts_for_openipc(camera_data, text, lang)

@app.route('/api/camera/<path:camera_id>/tts', methods=['POST'])
def camera_tts(camera_id):
    logger.info(f"Camera TTS endpoint called: {camera_id}")
    data = request.json or {}
    data['camera_id'] = camera_id
    return tts()

def _tts_for_beward(camera, text, lang):
    logger.info(f"Beward TTS to {camera['ip']}")
    
    with tempfile.NamedTemporaryFile(suffix='.alaw', delete=False) as tmp:
        alaw_path = tmp.name
    
    try:
        if not os.path.exists(TTS_GENERATE_BEWARD_SCRIPT):
            logger.error(f"Beward script not found: {TTS_GENERATE_BEWARD_SCRIPT}")
            return jsonify({"success": False, "error": "Beward script not found"}), 500
        
        # Генерируем A-law файл
        cmd = ["bash", TTS_GENERATE_BEWARD_SCRIPT, text, lang, alaw_path]
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.error(f"TTS generation failed: {result.stderr}")
            return jsonify({"success": False, "error": "TTS generation failed"}), 500
            
        if not os.path.exists(alaw_path):
            logger.error("TTS file not created")
            return jsonify({"success": False, "error": "TTS file not created"}), 500
        
        # Читаем аудио файл
        with open(alaw_path, 'rb') as f:
            audio_data = f.read()
        
        logger.info(f"Generated {len(audio_data)} bytes of A-law audio")
        
        # Сохраняем копию для отладки (каждое 5-е сообщение)
        if debug_counter % 5 == 0:
            debug_audio_path = f"/config/www/tts_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.alaw"
            try:
                shutil.copy2(alaw_path, debug_audio_path)
                logger.info(f"💾 Debug audio saved to {debug_audio_path}")
            except Exception as e:
                logger.error(f"Failed to save debug audio: {e}")
        
        # Формируем правильные заголовки как в документации Beward
        endpoint = camera.get('endpoint', '/cgi-bin/audio/transmit.cgi')
        url = f"http://{camera['ip']}{endpoint}"
        
        # Создаем базовую аутентификацию
        auth_str = base64.b64encode(f"{camera['username']}:{camera['password']}".encode()).decode()
        
        headers = {
            "Content-Type": "audio/basic",
            "Content-Length": str(len(audio_data)),
            "Connection": "Keep-Alive",
            "Cache-Control": "no-cache",
            "Authorization": f"Basic {auth_str}"
        }
        
        logger.debug(f"Sending to {url}")
        logger.debug(f"Headers: {headers}")
        
        # Отправляем POST запрос
        response = requests.post(url, headers=headers, data=audio_data, timeout=10)
        
        logger.info(f"Response status: {response.status_code}")
        logger.debug(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            logger.info(f"✅ TTS sent successfully to Beward")
            return jsonify({"success": True})
        else:
            logger.error(f"❌ TTS failed: HTTP {response.status_code}")
            try:
                error_text = response.text
                logger.error(f"Response body: {error_text[:200]}")
            except:
                pass
            return jsonify({"success": False, "error": f"HTTP {response.status_code}"}), 500
            
    except subprocess.TimeoutExpired:
        logger.error("TTS generation timeout")
        return jsonify({"success": False, "error": "TTS generation timeout"}), 500
    except Exception as e:
        logger.error(f"TTS error: {e}")
        logger.exception(e)
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # Очищаем временный файл
        if os.path.exists(alaw_path):
            try:
                os.unlink(alaw_path)
            except:
                pass

def _tts_for_openipc(camera, text, lang):
    logger.info(f"OpenIPC TTS to {camera['ip']}")
    
    with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False) as tmp:
        pcm_path = tmp.name
    
    try:
        if not os.path.exists(TTS_GENERATE_SCRIPT):
            return jsonify({"success": False, "error": "OpenIPC script not found"}), 500
        
        cmd = ["bash", TTS_GENERATE_SCRIPT, text, lang, pcm_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not os.path.exists(pcm_path):
            return jsonify({"success": False, "error": "TTS generation failed"}), 500
        
        endpoint = camera.get('endpoint', '/play_audio')
        url = f"http://{camera['ip']}{endpoint}"
        auth = (camera['username'], camera['password'])
        
        # Читаем аудио файл
        with open(pcm_path, 'rb') as f:
            audio_data = f.read()
        
        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(audio_data))
        }
        
        response = requests.post(url, headers=headers, data=audio_data, auth=auth, timeout=10)
        
        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"HTTP {response.status_code}"}), 500
            
    finally:
        if os.path.exists(pcm_path):
            os.unlink(pcm_path)

if __name__ == '__main__':
    logger.info("="*60)
    logger.info("Starting OpenIPC Bridge with configuration UI")
    logger.info("="*60)
    
    # Загружаем конфигурацию
    load_config()
    
    # Очищаем debug файл при старте
    if config['logging'].get('debug_qr', True):
        try:
            with open(QR_DEBUG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"QR Debug started at {datetime.now()}\n")
        except:
            pass
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)