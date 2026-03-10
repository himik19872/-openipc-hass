"""Клиент для локального аддона OpenIPC Bridge."""
import requests
import base64
import logging
from typing import Optional, List, Dict, Any

_LOGGER = logging.getLogger(__name__)

class OpenIPCBridgeClient:
    """Клиент для взаимодействия с локальным аддоном."""
    
    def __init__(self, host: str = "localhost", port: int = 5000):
        self.base_url = f"http://{host}:{port}"
        self._check_connection()
    
    def _check_connection(self) -> bool:
        """Проверка доступности аддона."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except Exception as e:
            _LOGGER.warning(f"Bridge addon not available: {e}")
            return False
    
    def text_to_speech(self, text: str, lang: str = "ru") -> Optional[str]:
        """Преобразование текста в речь (возвращает base64 аудио)."""
        try:
            response = requests.post(
                f"{self.base_url}/api/tts",
                json={"text": text, "lang": lang},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("audio")
            return None
        except Exception as e:
            _LOGGER.error(f"TTS error: {e}")
            return None
    
    def detect_barcodes(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        """Распознавание штрих-кодов на изображении."""
        try:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            response = requests.post(
                f"{self.base_url}/api/barcode",
                json={"image": image_b64},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return data.get("barcodes", [])
            return []
        except Exception as e:
            _LOGGER.error(f"Barcode detection error: {e}")
            return []
    
    def process_image(self, image_bytes: bytes, operation: str = "info", **kwargs) -> Dict[str, Any]:
        """Обработка изображения через OpenCV."""
        try:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            payload = {
                "image": image_b64,
                "operation": operation,
                **kwargs
            }
            response = requests.post(
                f"{self.base_url}/api/process_image",
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            return {"success": False, "error": "Request failed"}
        except Exception as e:
            _LOGGER.error(f"Image processing error: {e}")
            return {"success": False, "error": str(e)}