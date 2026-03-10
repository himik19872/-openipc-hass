"""API calls to OpenIPC cameras."""
import logging
import aiohttp

_LOGGER = logging.getLogger(__name__)

async def get_json_config(coordinator):
    """Get JSON configuration from camera."""
    url = f"http://{coordinator.host}:{coordinator.port}/api/v1/config.json"
    try:
        async with coordinator.session.get(url, auth=coordinator.auth, timeout=5) as response:
            if response.status == 200:
                try:
                    return await response.json()
                except:
                    return {}
            return {}
    except:
        return {}

async def get_metrics(coordinator):
    """Get Prometheus metrics from camera."""
    url = f"http://{coordinator.host}:{coordinator.port}/metrics"
    try:
        async with coordinator.session.get(url, auth=coordinator.auth, timeout=5) as response:
            if response.status == 200:
                text = await response.text()
                return _parse_metrics_text(text)
            return {}
    except:
        return {}

async def get_camera_status(coordinator):
    """Get camera status from HTML endpoint."""
    url = f"http://{coordinator.host}:{coordinator.port}/cgi-bin/status.cgi"
    return await _fetch_url(coordinator, url)

async def send_command(coordinator, command, params=None):
    """Send command to camera."""
    url = f"http://{coordinator.host}:{coordinator.port}{command}"
    if params:
        url += f"?{params}"
    try:
        async with coordinator.session.get(url, auth=coordinator.auth, timeout=5) as response:
            return response.status == 200
    except:
        return False

async def _fetch_url(coordinator, url):
    """Fetch URL with error handling."""
    try:
        async with coordinator.session.get(url, auth=coordinator.auth, timeout=5) as response:
            if response.status == 200:
                try:
                    text = await response.text(encoding='utf-8')
                    return {"raw": text, "status": response.status}
                except:
                    try:
                        text = await response.text(encoding='latin-1')
                        return {"raw": text, "status": response.status}
                    except:
                        return {}
            return {"status": response.status}
    except:
        return {}

def _parse_metrics_text(text):
    """Parse Prometheus metrics format."""
    metrics = {}
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        if '{' in line and '}' in line:
            name_part = line[:line.index('{')]
            labels_part = line[line.index('{')+1:line.index('}')]
            value_part = line[line.index('}')+1:].strip()
            
            labels = {}
            for label in labels_part.split(','):
                if '=' in label:
                    k, v = label.split('=', 1)
                    labels[k.strip()] = v.strip().strip('"')
            
            try:
                value = float(value_part)
            except:
                continue
            
            if name_part not in metrics:
                metrics[name_part] = {}
            
            if len(labels) == 1 and 'device' in labels:
                metrics[name_part][labels['device']] = value
            else:
                label_key = ','.join([f"{k}={v}" for k, v in labels.items()])
                if name_part not in metrics:
                    metrics[name_part] = {}
                metrics[name_part][label_key] = value
        else:
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                try:
                    value = float(parts[1])
                    metrics[name] = value
                except:
                    continue
    
    return metrics