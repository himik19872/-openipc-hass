"""Discovery module for OpenIPC cameras."""
import asyncio
import logging
import socket
import ipaddress
from typing import List, Dict, Optional, Tuple
import aiohttp
import async_timeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

# Для mDNS (если доступно)
try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

from .const import (
    DISCOVERY_PORT,
    DISCOVERY_TIMEOUT,
    SSDP_ST,
    BROADCAST_PORTS,
    DISCOVERY_ENDPOINTS,
    OPENIPC_MAC_PREFIXES,
    MDNS_SERVICE,
)

_LOGGER = logging.getLogger(__name__)

class OpenICPCDiscovery:
    """Class to discover OpenIPC cameras on the network."""

    def __init__(self, hass: HomeAssistant):
        """Initialize discovery."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.discovered_devices = []
        self._scan_lock = asyncio.Lock()

    async def discover_all(self) -> List[Dict]:
        """Run all discovery methods and return unique devices."""
        async with self._scan_lock:
            self.discovered_devices = []
            
            # Run all discovery methods in parallel
            tasks = [
                self.ssdp_discovery(),
                self.broadcast_discovery(),
                self.arp_scan_discovery(),
            ]
            
            # Add mDNS if available
            if ZEROCONF_AVAILABLE:
                tasks.append(self.mdns_discovery())
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    _LOGGER.debug("Discovery method failed: %s", result)
                elif isinstance(result, list):
                    self.discovered_devices.extend(result)
            
            # Remove duplicates by IP
            unique_devices = {}
            for device in self.discovered_devices:
                ip = device.get("ip")
                if ip and ip not in unique_devices:
                    unique_devices[ip] = device
            
            # Verify each device is actually an OpenIPC camera
            verified_devices = []
            for device in unique_devices.values():
                if await self.verify_device(device):
                    verified_devices.append(device)
            
            _LOGGER.info("Discovered %d OpenIPC cameras", len(verified_devices))
            return verified_devices

    async def ssdp_discovery(self) -> List[Dict]:
        """Discover cameras via SSDP."""
        _LOGGER.debug("Starting SSDP discovery")
        discovered = []
        
        # Create UDP socket for SSDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(2)
        
        # SSDP discovery message
        message = "\r\n".join([
            'M-SEARCH * HTTP/1.1',
            'HOST: 239.255.255.250:1900',
            'MAN: "ssdp:discover"',
            'MX: 2',
            f'ST: {SSDP_ST}',
            ''
        ]).encode('utf-8')
        
        try:
            # Send discovery
            sock.sendto(message, ('239.255.255.250', 1900))
            
            # Listen for responses
            start_time = self.hass.loop.time()
            while self.hass.loop.time() - start_time < 5:
                try:
                    data, addr = sock.recvfrom(1024)
                    response = data.decode('utf-8', errors='ignore')
                    
                    # Check if it might be an OpenIPC camera
                    if 'openipc' in response.lower() or 'camera' in response.lower():
                        ip = addr[0]
                        location = self._extract_location(response)
                        
                        if location:
                            device_info = {
                                "ip": ip,
                                "port": 80,
                                "source": "ssdp",
                                "location": location,
                                "headers": self._parse_ssdp_response(response),
                            }
                            discovered.append(device_info)
                            _LOGGER.debug("SSDP discovered: %s", ip)
                            
                except socket.timeout:
                    continue
                except Exception as e:
                    _LOGGER.debug("SSDP receive error: %s", e)
                    
        except Exception as e:
            _LOGGER.debug("SSDP discovery error: %s", e)
        finally:
            sock.close()
        
        return discovered

    async def broadcast_discovery(self) -> List[Dict]:
        """Discover cameras by probing common ports."""
        _LOGGER.debug("Starting broadcast discovery")
        discovered = []
        
        # Get local network
        local_ip = await self._get_local_ip()
        if not local_ip:
            return discovered
        
        network = self._get_network(local_ip)
        if not network:
            return discovered
        
        # Scan common camera IPs (first 20 addresses for speed)
        hosts = list(network.hosts())[:20]
        
        # Create tasks for probing
        tasks = []
        for host in hosts:
            ip = str(host)
            if ip == local_ip:
                continue
            tasks.append(self._probe_host(ip))
        
        # Run probes
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict) and result.get("ip"):
                discovered.append(result)
        
        return discovered

    async def arp_scan_discovery(self) -> List[Dict]:
        """Discover cameras via ARP scan (requires root on some systems)."""
        _LOGGER.debug("Starting ARP scan discovery")
        discovered = []
        
        try:
            # Try to use arp-scan if available
            process = await asyncio.create_subprocess_exec(
                "arp-scan", "--localnet", "--retry=1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                lines = stdout.decode().split('\n')
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        mac = parts[1] if len(parts) > 1 else ""
                        
                        # Check if MAC matches known OpenIPC prefixes
                        if any(mac.upper().startswith(prefix.upper()) for prefix in OPENIPC_MAC_PREFIXES):
                            device_info = {
                                "ip": ip,
                                "mac": mac,
                                "port": 80,
                                "source": "arp",
                            }
                            discovered.append(device_info)
                            _LOGGER.debug("ARP discovered: %s (%s)", ip, mac)
        except Exception as e:
            _LOGGER.debug("ARP scan failed: %s", e)
        
        return discovered

    async def mdns_discovery(self) -> List[Dict]:
        """Discover cameras via mDNS (Zeroconf)."""
        if not ZEROCONF_AVAILABLE:
            return []
        
        _LOGGER.debug("Starting mDNS discovery")
        discovered = []
        
        class OpenIPCListener(ServiceListener):
            def __init__(self):
                self.services = []
            
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    self.services.append(info)
            
            def update_service(self, zc, type_, name):
                pass
            
            def remove_service(self, zc, type_, name):
                pass
        
        try:
            zeroconf = Zeroconf()
            listener = OpenIPCListener()
            browser = ServiceBrowser(zeroconf, MDNS_SERVICE, listener)
            
            # Wait for responses
            await asyncio.sleep(3)
            
            for service in listener.services:
                if service.addresses:
                    ip = socket.inet_ntoa(service.addresses[0])
                    port = service.port
                    
                    # Check if it might be OpenIPC
                    if service.name and ('openipc' in service.name.lower() or 'camera' in service.name.lower()):
                        device_info = {
                            "ip": ip,
                            "port": port,
                            "source": "mdns",
                            "name": service.name,
                            "properties": service.properties,
                        }
                        discovered.append(device_info)
                        _LOGGER.debug("mDNS discovered: %s:%d", ip, port)
            
            zeroconf.close()
            
        except Exception as e:
            _LOGGER.debug("mDNS discovery error: %s", e)
        
        return discovered

    async def _probe_host(self, ip: str) -> Optional[Dict]:
        """Probe a single host for OpenIPC API."""
        for port in BROADCAST_PORTS:
            for endpoint in DISCOVERY_ENDPOINTS:
                url = f"http://{ip}:{port}{endpoint}"
                try:
                    async with async_timeout.timeout(1):
                        async with self.session.get(url) as response:
                            if response.status == 200:
                                # Try to verify it's OpenIPC
                                text = await response.text()
                                if 'openipc' in text.lower() or 'majestic' in text.lower():
                                    _LOGGER.debug("Found OpenIPC at %s:%d via %s", ip, port, endpoint)
                                    return {
                                        "ip": ip,
                                        "port": port,
                                        "source": "probe",
                                        "endpoint": endpoint,
                                    }
                except:
                    continue
        return None

    async def verify_device(self, device: Dict) -> bool:
        """Verify that a discovered device is actually an OpenIPC camera."""
        ip = device["ip"]
        port = device.get("port", 80)
        
        # Try multiple endpoints to verify
        verification_endpoints = [
            (f"http://{ip}:{port}/cgi-bin/status.cgi", "openipc"),
            (f"http://{ip}:{port}/metrics", "node_"),
            (f"http://{ip}:{port}/api/v1/config.json", "majestic"),
            (f"http://{ip}:{port}/image.jpg", None),  # Just check if returns image
        ]
        
        for url, expected_text in verification_endpoints:
            try:
                async with async_timeout.timeout(2):
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            if expected_text:
                                text = await response.text()
                                if expected_text in text.lower():
                                    device["verified_by"] = url
                                    return True
                            else:
                                # For image.jpg, check content type
                                content_type = response.headers.get('Content-Type', '')
                                if 'image' in content_type:
                                    device["verified_by"] = url
                                    return True
            except:
                continue
        
        return False

    async def _get_local_ip(self) -> Optional[str]:
        """Get local IP address."""
        try:
            # Create temporary connection to get local IP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
            sock.close()
            return local_ip
        except:
            return None

    def _get_network(self, ip: str) -> Optional[ipaddress.IPv4Network]:
        """Get network from IP address (assumes /24)."""
        try:
            return ipaddress.IPv4Network(f"{ip}/24", strict=False)
        except:
            return None

    def _extract_location(self, ssdp_response: str) -> Optional[str]:
        """Extract LOCATION header from SSDP response."""
        for line in ssdp_response.split('\n'):
            if line.lower().startswith('location:'):
                return line.split(':', 1)[1].strip()
        return None

    def _parse_ssdp_response(self, response: str) -> Dict:
        """Parse SSDP response headers."""
        headers = {}
        for line in response.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        return headers