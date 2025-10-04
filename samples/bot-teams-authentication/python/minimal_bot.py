#!/usr/bin/env python3
"""
Minimal Teams Bot with HTTP Authentication Logging
Fixed version without problematic dependencies
"""

import logging
from aiohttp import web
from aiohttp.web import Request, Response

# Import and enable HTTP logging FIRST
from simple_http_logger import enable_http_logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable HTTP request/response logging for all outgoing HTTP calls
enable_http_logging()

async def messages(req: Request) -> Response:
    """Handle incoming messages - minimal bot endpoint."""
    logger.info("Bot received a message")
    
    # Your bot's message handling logic would go here
    # This is where authentication requests would be triggered
    
    return Response(status=200, text="OK")

def create_app():
    """Create the web app."""
    app = web.Application()
    app.router.add_post("/api/messages", messages)
    return app

if __name__ == "__main__":
    print("Starting Teams Bot with HTTP Authentication Logging...")
    print("OAuth authentication requests will be logged with '=== OAUTH HTTP REQUEST ===' headers")
    
    APP = create_app()
    
    try:
        # Try to start on port 3978 (default Bot Framework port)
        web.run_app(APP, host="localhost", port=3978)
    except OSError as e:
        if "address already in use" in str(e).lower():
            print(f"Port 3978 is busy, trying port 3979...")
            web.run_app(APP, host="localhost", port=3979)
        else:
            raise e