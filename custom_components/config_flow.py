"""Config flow for OpenIPC integration."""
import logging
import voluptuous as vol
import aiohttp
import asyncio
import socket

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.data_entry_flow import AbortFlow

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_RTSP_PORT,
    DEFAULT_USERNAME,
    CONF_RTSP_PORT,
    CONF_STREAM_PROFILE,
    # Device types
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_OPENIPC,
    DEVICE_TYPE_BEWARD,
    DEVICE_TYPE_VIVOTEK,
)

_LOGGER = logging.getLogger(__name__)

# Расширенный список возможных эндпоинтов API
OPENIPC_ENDPOINTS = [
    "/cgi-bin/api.cgi?cmd=Status",
    "/cgi-bin/status",
    "/api/info",
    "/status",
    "/cgi-bin/config.cgi?action=get",
    "/cgi-bin/api.cgi?cmd=SystemInfo",
    "/api/v1/config.json",
    "/metrics",
    "/image.jpg",
]

# Специфичные эндпоинты для Beward (на основе реального ответа камеры)
BEWARD_ENDPOINTS = [
    "/cgi-bin/image.cgi",                    # Beward snapshot
    "/cgi-bin/status.cgi",                   # Beward status
    "/cgi-bin/systeminfo_cgi?action=get",    # Beward system info
    "/cgi-bin/intercom_cgi?action=status",   # Beward intercom status
    "/login.asp",                             # Beward login page (после редиректа)
]

# Специфичные эндпоинты для Vivotek
VIVOTEK_ENDPOINTS = [
    "/cgi-bin/video.jpg",                     # Vivotek snapshot
    "/cgi-bin/hello",                          # Vivotek test endpoint
    "/cgi-bin/viewer/video.mjpg",              # Vivotek MJPEG stream
    "/cgi-bin/camctrl/camctrl.cgi",            # Vivotek PTZ control
]

# Схема данных для основной формы настройки
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="OpenIPC Camera"): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_STREAM_PROFILE, default="main"): vol.In(["main", "sub"]),
        vol.Required(CONF_DEVICE_TYPE, default=DEVICE_TYPE_OPENIPC): vol.In({
            DEVICE_TYPE_OPENIPC: "OpenIPC",
            DEVICE_TYPE_BEWARD: "Beward (doorbell)",
            DEVICE_TYPE_VIVOTEK: "Vivotek (PTZ camera)",
        }),
    }
)

async def check_host_availability(host, port):
    """Check if host is reachable."""
    try:
        # Пробуем разрешить DNS имя
        await asyncio.get_event_loop().getaddrinfo(host, port)
        
        # Пробуем открыть сокет
        reader, writer = await asyncio.open_connection(host, port)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as err:
        _LOGGER.debug("Host %s not available on port %s: %s", host, port, err)
        return False

async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    auth = aiohttp.BasicAuth(data[CONF_USERNAME], data[CONF_PASSWORD])
    
    _LOGGER.debug("Attempting to validate connection to %s:%s as %s", 
                  data[CONF_HOST], data[CONF_PORT], data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_OPENIPC))
    
    # Сначала проверяем базовую доступность хоста
    host_available = await check_host_availability(data[CONF_HOST], data[CONF_PORT])
    if not host_available:
        raise CannotConnect(f"Cannot connect to camera at {data[CONF_HOST]}:{data[CONF_PORT]}")
    
    # Определяем тип устройства
    device_type = data.get(CONF_DEVICE_TYPE, DEVICE_TYPE_OPENIPC)
    
    # Пробуем разные порты, если указанный не работает (для диагностики)
    ports_to_try = [data[CONF_PORT], 80, 8080, 443, 554]
    
    # Сначала пробуем зайти на главную страницу для определения типа
    for port in set(ports_to_try):
        try:
            url = f"http://{data[CONF_HOST]}:{port}/"
            _LOGGER.debug("Trying main page: %s", url)
            
            async with session.get(url, auth=auth, timeout=5, allow_redirects=True) as response:
                _LOGGER.debug("Main page returned status %s, final URL: %s", 
                             response.status, response.url)
                
                # Если есть редирект на login.asp - это Beward
                if 'login.asp' in str(response.url):
                    _LOGGER.info("✅ Beward camera detected via login.asp redirect on port %d", port)
                    
                    # Проверяем специфичный Beward эндпоинт для подтверждения
                    test_url = f"http://{data[CONF_HOST]}:{port}/cgi-bin/image.cgi"
                    try:
                        async with session.get(test_url, auth=auth, timeout=3) as img_response:
                            if img_response.status == 200:
                                content_type = img_response.headers.get('Content-Type', '')
                                if 'image' in content_type:
                                    _LOGGER.info("✅ Beward camera confirmed via image.cgi")
                                    # Обновляем порт в данных
                                    data[CONF_PORT] = port
                                    return {
                                        "title": data[CONF_NAME], 
                                        "unique_id": f"beward_{data[CONF_HOST]}"
                                    }
                    except:
                        pass
                    
                    # Если image.cgi не сработал, но есть login.asp - всё равно считаем Beward
                    data[CONF_PORT] = port
                    return {
                        "title": data[CONF_NAME], 
                        "unique_id": f"beward_{data[CONF_HOST]}"
                    }
                
                # Проверяем заголовок Server
                server = response.headers.get('Server', '').lower()
                if 'beward' in server:
                    _LOGGER.info("✅ Beward camera detected via Server header on port %d", port)
                    data[CONF_PORT] = port
                    return {"title": data[CONF_NAME], "unique_id": f"beward_{data[CONF_HOST]}"}
                if 'vivotek' in server:
                    _LOGGER.info("✅ Vivotek camera detected via Server header on port %d", port)
                    data[CONF_PORT] = port
                    return {"title": data[CONF_NAME], "unique_id": f"vivotek_{data[CONF_HOST]}"}
                
                # Проверяем содержимое страницы
                if response.status == 200:
                    text = await response.text()
                    if 'Beward' in text or 'beward' in text.lower():
                        _LOGGER.info("✅ Beward camera detected via page content on port %d", port)
                        data[CONF_PORT] = port
                        return {"title": data[CONF_NAME], "unique_id": f"beward_{data[CONF_HOST]}"}
                    if 'VIVOTEK' in text:
                        _LOGGER.info("✅ Vivotek camera detected via page content on port %d", port)
                        data[CONF_PORT] = port
                        return {"title": data[CONF_NAME], "unique_id": f"vivotek_{data[CONF_HOST]}"}
                        
        except Exception as err:
            _LOGGER.debug("Main page check on port %d failed: %s", port, err)
            continue
    
    # Если главная страница не помогла, пробуем специфичные эндпоинты
    # Используем исходный порт из данных
    port = data[CONF_PORT]
    
    # Выбираем эндпоинты в зависимости от типа
    if device_type == DEVICE_TYPE_BEWARD:
        endpoints_to_try = BEWARD_ENDPOINTS + ["/", "/index.html"]
        _LOGGER.debug("Trying Beward endpoints: %s", endpoints_to_try)
    elif device_type == DEVICE_TYPE_VIVOTEK:
        endpoints_to_try = VIVOTEK_ENDPOINTS + ["/", "/index.html"]
        _LOGGER.debug("Trying Vivotek endpoints: %s", endpoints_to_try)
    else:
        endpoints_to_try = OPENIPC_ENDPOINTS + ["/", "/index.html"]
        _LOGGER.debug("Trying OpenIPC endpoints")
    
    # Пробуем эндпоинты
    last_error = None
    for endpoint in endpoints_to_try:
        # Пропускаем RTSP эндпоинты для HTTP проверки
        if endpoint.startswith('/av') or endpoint.endswith('.sdp'):
            continue
            
        url = f"http://{data[CONF_HOST]}:{port}{endpoint}"
        _LOGGER.debug("Trying endpoint: %s", url)
        
        try:
            async with session.get(url, auth=auth, timeout=5, allow_redirects=True) as response:
                _LOGGER.debug("Endpoint %s returned status %s, Content-Type: %s", 
                             endpoint, response.status, response.headers.get('Content-Type', ''))
                
                if response.status == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    
                    # Для Beward - проверяем специфичные признаки
                    if device_type == DEVICE_TYPE_BEWARD:
                        # Если получили изображение с image.cgi
                        if endpoint == "/cgi-bin/image.cgi" and 'image' in content_type:
                            _LOGGER.info("✅ Beward camera confirmed via image endpoint")
                            return {"title": data[CONF_NAME], "unique_id": f"beward_{data[CONF_HOST]}"}
                        
                        # Проверяем login.asp
                        if endpoint == "/login.asp" or 'login.asp' in str(response.url):
                            _LOGGER.info("✅ Beward camera confirmed via login.asp")
                            return {"title": data[CONF_NAME], "unique_id": f"beward_{data[CONF_HOST]}"}
                        
                        # Проверяем HTML страницу на наличие признаков Beward
                        if 'text/html' in content_type:
                            text = await response.text()
                            if any(x in text for x in ['Beward', 'intercom', 'door', 'домофон']):
                                _LOGGER.info("✅ Beward camera confirmed via HTML content")
                                return {"title": data[CONF_NAME], "unique_id": f"beward_{data[CONF_HOST]}"}
                    
                    # Для Vivotek
                    elif device_type == DEVICE_TYPE_VIVOTEK:
                        if endpoint == "/cgi-bin/hello":
                            text = await response.text()
                            if 'hello' in text.lower():
                                _LOGGER.info("✅ Vivotek camera confirmed via hello endpoint")
                                return {"title": data[CONF_NAME], "unique_id": f"vivotek_{data[CONF_HOST]}"}
                        
                        if 'image' in content_type or 'mjpeg' in content_type:
                            _LOGGER.info("✅ Vivotek camera confirmed via %s", endpoint)
                            return {"title": data[CONF_NAME], "unique_id": f"vivotek_{data[CONF_HOST]}"}
                        
                        if 'text/html' in content_type:
                            text = await response.text()
                            if 'VIVOTEK' in text:
                                _LOGGER.info("✅ Vivotek camera confirmed via HTML")
                                return {"title": data[CONF_NAME], "unique_id": f"vivotek_{data[CONF_HOST]}"}
                    
                    # Для OpenIPC
                    else:
                        if endpoint == '/metrics' or 'json' in content_type:
                            try:
                                text = await response.text()
                                if any(x in text for x in ['openipc', 'majestic', 'node_']):
                                    return {"title": data[CONF_NAME], "unique_id": f"openipc_{data[CONF_HOST]}"}
                            except:
                                pass
                        
                        if endpoint == '/cgi-bin/status.cgi' and 'text/html' in content_type:
                            text = await response.text()
                            if 'Uptime' in text or 'CPU' in text:
                                return {"title": data[CONF_NAME], "unique_id": f"openipc_{data[CONF_HOST]}"}
                    
                elif response.status == 401:
                    raise InvalidAuth("Authentication failed")
                    
        except aiohttp.ClientConnectorError as err:
            last_error = f"Connection error: {err}"
            _LOGGER.debug("Connection error for %s: %s", endpoint, err)
            continue
        except asyncio.TimeoutError:
            last_error = "Timeout"
            _LOGGER.debug("Timeout for %s", endpoint)
            continue
        except aiohttp.ClientResponseError as err:
            last_error = f"HTTP error: {err.status}"
            _LOGGER.debug("HTTP error for %s: %s", endpoint, err)
            continue
        except Exception as err:
            last_error = str(err)
            _LOGGER.debug("Error for %s: %s", endpoint, err)
            continue
    
    # Если ничего не сработало, но хост доступен - возможно это Beward/Vivotek с нестандартными настройками
    _LOGGER.warning("Could not determine camera type at %s, but host is reachable", data[CONF_HOST])
    _LOGGER.warning("Last error: %s", last_error)
    
    # Если пользователь выбрал конкретный тип, пробуем создать запись
    if device_type != DEVICE_TYPE_OPENIPC:
        _LOGGER.info("Creating entry as %s based on user selection", device_type)
        return {"title": data[CONF_NAME], "unique_id": f"{device_type}_{data[CONF_HOST]}"}
    
    raise CannotConnect(f"Could not establish connection to camera at {data[CONF_HOST]}:{port}")

class OpenIPCConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenIPC."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = []
        self.camera_data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            self.camera_data.update(user_input)
            
            try:
                # Проверяем уникальность
                unique_id = f"{user_input[CONF_DEVICE_TYPE]}_{user_input[CONF_HOST]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                
                # Валидируем ввод
                info = await validate_input(self.hass, user_input)
                
                # Создаем запись
                return self.async_create_entry(
                    title=self.camera_data[CONF_NAME], 
                    data=self.camera_data
                )
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
                _LOGGER.error("Cannot connect to camera at %s", user_input[CONF_HOST])
            except InvalidAuth:
                errors["base"] = "invalid_auth"
                _LOGGER.error("Invalid authentication for camera at %s", user_input[CONF_HOST])
            except AbortFlow:
                errors["base"] = "already_configured"
                _LOGGER.error("Camera at %s already configured", user_input[CONF_HOST])
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", 
            data_schema=DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "host": "192.168.1.10 (Beward)",
                "port": "80",
            }
        )

    async def async_step_ssdp(self, discovery_info):
        """Handle SSDP discovery."""
        _LOGGER.debug("SSDP discovery: %s", discovery_info)
        
        try:
            # Извлекаем информацию из SSDP
            host = None
            port = DEFAULT_PORT
            
            # Пробуем получить host из разных полей
            if hasattr(discovery_info, 'ssdp_location'):
                from urllib.parse import urlparse
                parsed = urlparse(discovery_info.ssdp_location)
                host = parsed.hostname
                port = parsed.port or DEFAULT_PORT
            elif 'ssdp_location' in discovery_info:
                from urllib.parse import urlparse
                parsed = urlparse(discovery_info['ssdp_location'])
                host = parsed.hostname
                port = parsed.port or DEFAULT_PORT
            
            if not host:
                _LOGGER.debug("Could not extract host from SSDP discovery")
                return self.async_abort(reason="no_host")
            
            # Определяем возможный тип устройства по SSDP
            device_type = DEVICE_TYPE_OPENIPC
            manufacturer = discovery_info.get('manufacturer', '').lower()
            if 'beward' in manufacturer:
                device_type = DEVICE_TYPE_BEWARD
            elif 'vivotek' in manufacturer:
                device_type = DEVICE_TYPE_VIVOTEK
            
            # Проверяем, не настроена ли уже камера
            unique_id = f"{device_type}_{host}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            # Сохраняем информацию об обнаруженном устройстве
            self.discovered_devices.append({
                "ip": host,
                "port": port,
                "name": f"Camera {host}",
                "source": "ssdp",
            })
            
            # Заполняем данные камеры
            self.camera_data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: f"Camera {host}",
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: "",
                CONF_RTSP_PORT: DEFAULT_RTSP_PORT,
                CONF_STREAM_PROFILE: "main",
                CONF_DEVICE_TYPE: device_type,
            }
            
            # Показываем форму подтверждения
            return await self.async_step_confirm()
            
        except AbortFlow:
            raise
        except Exception as err:
            _LOGGER.error("SSDP discovery error: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_zeroconf(self, discovery_info):
        """Handle zeroconf/mDNS discovery."""
        _LOGGER.debug("Zeroconf discovery: %s", discovery_info)
        
        try:
            # Извлекаем информацию из Zeroconf
            host = None
            port = DEFAULT_PORT
            name = "Camera"
            device_type = DEVICE_TYPE_OPENIPC
            
            if hasattr(discovery_info, 'host'):
                host = discovery_info.host
            elif hasattr(discovery_info, 'ip_address') and discovery_info.ip_address:
                host = str(discovery_info.ip_address)
            
            if hasattr(discovery_info, 'port'):
                port = discovery_info.port
            
            if hasattr(discovery_info, 'name'):
                name = discovery_info.name.split('.')[0]
            
            if hasattr(discovery_info, 'type'):
                service_type = discovery_info.type.lower()
                if '_beward' in service_type:
                    device_type = DEVICE_TYPE_BEWARD
                elif '_onvif' in service_type or '_vivotek' in service_type:
                    device_type = DEVICE_TYPE_VIVOTEK
            
            if not host:
                _LOGGER.debug("Could not extract host from Zeroconf discovery")
                return self.async_abort(reason="no_host")
            
            # Проверяем, не настроена ли уже камера
            unique_id = f"{device_type}_{host}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            # Сохраняем информацию об обнаруженном устройстве
            self.discovered_devices.append({
                "ip": host,
                "port": port,
                "name": name,
                "source": "zeroconf",
            })
            
            # Заполняем данные камеры
            self.camera_data = {
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: "",
                CONF_RTSP_PORT: DEFAULT_RTSP_PORT,
                CONF_STREAM_PROFILE: "main",
                CONF_DEVICE_TYPE: device_type,
            }
            
            # Показываем форму подтверждения
            return await self.async_step_confirm()
            
        except AbortFlow:
            raise
        except Exception as err:
            _LOGGER.error("Zeroconf discovery error: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_confirm(self, user_input=None):
        """Confirm discovery."""
        if user_input is not None:
            # Создаем запись
            return self.async_create_entry(
                title=self.camera_data[CONF_NAME], 
                data=self.camera_data
            )
        
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self.camera_data[CONF_NAME],
                "host": self.camera_data[CONF_HOST],
                "type": self.camera_data[CONF_DEVICE_TYPE],
            }
        )

    async def async_step_import(self, user_input=None):
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""