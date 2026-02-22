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
)

_LOGGER = logging.getLogger(__name__)

# Расширенный список возможных эндпоинтов API
API_ENDPOINTS = [
    "/cgi-bin/api.cgi?cmd=Status",
    "/cgi-bin/status",
    "/api/info",
    "/status",
    "/cgi-bin/config.cgi?action=get",
    "/cgi-bin/api.cgi?cmd=SystemInfo",
    "/api/v1/config.json",
    "/metrics",
]

# Схема данных для формы настройки
DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="OpenIPC Camera"): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_RTSP_PORT, default=DEFAULT_RTSP_PORT): int,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_STREAM_PROFILE, default="main"): vol.In(["main", "sub"]),
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
    except:
        return False

async def validate_input(hass: HomeAssistant, data):
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    auth = aiohttp.BasicAuth(data[CONF_USERNAME], data[CONF_PASSWORD])
    
    _LOGGER.debug("Attempting to validate connection to %s:%s", 
                  data[CONF_HOST], data[CONF_PORT])
    
    # Сначала проверяем базовую доступность хоста
    host_available = await check_host_availability(data[CONF_HOST], data[CONF_PORT])
    if not host_available:
        _LOGGER.error("Host %s is not reachable on port %s", 
                      data[CONF_HOST], data[CONF_PORT])
        raise CannotConnect(
            f"Cannot connect to camera at {data[CONF_HOST]}. "
            f"Check if the IP address is correct and camera is powered on. "
            f"Also verify that port {data[CONF_PORT]} is open."
        )
    
    # Пробуем разные эндпоинты
    last_error = None
    for endpoint in API_ENDPOINTS:
        url = f"http://{data[CONF_HOST]}:{data[CONF_PORT]}{endpoint}"
        _LOGGER.debug("Trying endpoint: %s", url)
        
        try:
            async with session.get(url, auth=auth, timeout=5) as response:
                _LOGGER.debug("Endpoint %s returned status %s", endpoint, response.status)
                
                if response.status == 200:
                    try:
                        json_response = await response.json()
                        _LOGGER.debug("Successfully connected to camera via %s", endpoint)
                        return {
                            "title": data[CONF_NAME], 
                            "unique_id": f"openipc_{data[CONF_HOST]}"
                        }
                    except:
                        # Получили ответ, но это не JSON - возможно, это HTML страница
                        text = await response.text()
                        if "openipc" in text.lower() or "camera" in text.lower() or "majestic" in text.lower():
                            _LOGGER.debug("Found OpenIPC web interface")
                            return {
                                "title": data[CONF_NAME], 
                                "unique_id": f"openipc_{data[CONF_HOST]}"
                            }
                        else:
                            _LOGGER.debug("Response is not JSON and doesn't look like OpenIPC")
                            
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
        except Exception as err:
            last_error = str(err)
            _LOGGER.debug("Error for %s: %s", endpoint, err)
            continue
    
    # Если ни один эндпоинт не сработал
    if last_error:
        raise CannotConnect(
            f"Connected to {data[CONF_HOST]} but camera API not responding. "
            f"Last error: {last_error}. Make sure this is an OpenIPC camera."
        )
    else:
        raise CannotConnect(
            f"Could not establish connection to camera API at {data[CONF_HOST]}. "
            f"Please verify the camera is running OpenIPC firmware."
        )

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for OpenIPC."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                # Проверяем уникальность
                await self.async_set_unique_id(f"openipc_{user_input[CONF_HOST]}")
                self._abort_if_unique_id_configured()
                
                # Валидируем ввод
                info = await validate_input(self.hass, user_input)
                
                # Создаем запись
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                # Камера уже настроена
                errors["base"] = "already_configured"
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", 
            data_schema=DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "host": "192.168.1.103",
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
            
            # Проверяем, не настроена ли уже камера
            await self.async_set_unique_id(f"openipc_{host}")
            self._abort_if_unique_id_configured()
            
            # Сохраняем информацию об обнаруженном устройстве
            self.discovered_devices.append({
                "ip": host,
                "port": port,
                "name": f"OpenIPC {host}",
                "source": "ssdp",
            })
            
            # Показываем форму с предзаполненными данными
            return await self.async_step_user({
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: f"OpenIPC {host}",
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: "",
                CONF_RTSP_PORT: DEFAULT_RTSP_PORT,
                CONF_STREAM_PROFILE: "main",
            })
            
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
            name = "OpenIPC Camera"
            
            # ZeroconfServiceInfo имеет атрибуты, а не словарь
            if hasattr(discovery_info, 'host'):
                host = discovery_info.host
            elif hasattr(discovery_info, 'ip_address') and discovery_info.ip_address:
                host = str(discovery_info.ip_address)
            
            if hasattr(discovery_info, 'port'):
                port = discovery_info.port
            
            if hasattr(discovery_info, 'name'):
                name = discovery_info.name.split('.')[0]
            
            if not host:
                _LOGGER.debug("Could not extract host from Zeroconf discovery")
                return self.async_abort(reason="no_host")
            
            # Проверяем, не настроена ли уже камера
            await self.async_set_unique_id(f"openipc_{host}")
            self._abort_if_unique_id_configured()
            
            # Сохраняем информацию об обнаруженном устройстве
            self.discovered_devices.append({
                "ip": host,
                "port": port,
                "name": name,
                "source": "zeroconf",
            })
            
            # Показываем форму с предзаполненными данными
            return await self.async_step_user({
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_NAME: name,
                CONF_USERNAME: DEFAULT_USERNAME,
                CONF_PASSWORD: "",
                CONF_RTSP_PORT: DEFAULT_RTSP_PORT,
                CONF_STREAM_PROFILE: "main",
            })
            
        except AbortFlow:
            raise
        except Exception as err:
            _LOGGER.error("Zeroconf discovery error: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_import(self, user_input=None):
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)

class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""