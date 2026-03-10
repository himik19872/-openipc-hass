#!/usr/bin/env python3
import logging
import sys
import argparse
from aiohttp import web

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger("openipc_bridge")

async def handle_root(request):
    return web.json_response({
        "name": "OpenIPC Bridge Local",
        "status": "running",
        "version": "1.0.0-local"
    })

async def handle_health(request):
    return web.json_response({
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.now().isoformat()
    })

async def start_server(host='0.0.0.0', port=8123):
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    _LOGGER.info(f"✅ Server started on http://{host}:{port}")
    return runner

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8123)
    args = parser.parse_args()
    
    import asyncio
    import signal
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    runner = loop.run_until_complete(start_server(args.host, args.port))
    
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(runner.cleanup())
        loop.close()

if __name__ == "__main__":
    main()