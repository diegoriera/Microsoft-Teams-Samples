# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import json
import asyncio
from typing import Any, Dict, Optional
from aiohttp import ClientSession, ClientResponse, ClientTimeout
import aiohttp


class HTTPLogger:
    """HTTP request/response logger for tracking all outgoing HTTP requests."""
    
    def __init__(self, logger_name: str = "HTTPLogger"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Create formatter for HTTP logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Ensure we have a handler
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def log_request(self, method: str, url: str, headers: Dict[str, Any], 
                         body: Optional[str], request_id: str):
        """Log outgoing HTTP request details."""
        # Sanitize sensitive headers
        sanitized_headers = self._sanitize_headers(headers)
        
        self.logger.info("=== Outgoing HTTP Request ===")
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Method: {method}")
        self.logger.info(f"URL: {url}")
        self.logger.info(f"Headers: {json.dumps(sanitized_headers, indent=2)}")
        
        if body:
            # Try to format JSON body nicely, fallback to string
            try:
                if isinstance(body, (str, bytes)):
                    if isinstance(body, bytes):
                        body = body.decode('utf-8', errors='ignore')
                    json_body = json.loads(body)
                    self.logger.info(f"Body: {json.dumps(json_body, indent=2)}")
                else:
                    self.logger.info(f"Body: {json.dumps(body, indent=2)}")
            except (json.JSONDecodeError, TypeError):
                self.logger.info(f"Body (raw): {str(body)}")
        else:
            self.logger.info("Body: (empty)")
        
        self.logger.info("=== End Request ===")

    async def log_response(self, status: int, headers: Dict[str, Any], 
                          body: Optional[str], request_id: str, 
                          response_time_ms: float):
        """Log HTTP response details."""
        # Sanitize sensitive headers
        sanitized_headers = self._sanitize_headers(headers)
        
        self.logger.info("=== HTTP Response ===")
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Status Code: {status}")
        self.logger.info(f"Response Time: {response_time_ms:.2f}ms")
        self.logger.info(f"Headers: {json.dumps(sanitized_headers, indent=2)}")
        
        if body:
            # Try to format JSON response nicely, fallback to string
            try:
                if isinstance(body, (str, bytes)):
                    if isinstance(body, bytes):
                        body = body.decode('utf-8', errors='ignore')
                    json_body = json.loads(body)
                    self.logger.info(f"Body: {json.dumps(json_body, indent=2)}")
                else:
                    self.logger.info(f"Body: {json.dumps(body, indent=2)}")
            except (json.JSONDecodeError, TypeError):
                self.logger.info(f"Body (raw): {str(body)}")
        else:
            self.logger.info("Body: (empty)")
            
        self.logger.info("=== End Response ===")

    def _sanitize_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask sensitive header values."""
        sensitive_headers = {
            'auth', 'x-api-key', 'x-auth-token', 
            'cookie', 'set-cookie', 'x-csrf-token', 'x-forwarded-for'
        }
        
        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in sensitive_headers:
                sanitized[key] = "[REDACTED]"
            elif 'token' in key_lower or 'secret' in key_lower or 'password' in key_lower:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized


class LoggingClientSession(ClientSession):
    """aiohttp ClientSession wrapper that logs all HTTP requests and responses."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_logger = HTTPLogger("OutgoingHTTP")
        self._request_counter = 0

    def _get_request_id(self) -> str:
        """Generate unique request ID for tracking."""
        self._request_counter += 1
        return f"req_{self._request_counter}_{id(self)}"

    async def _request(self, method: str, url, **kwargs) -> ClientResponse:
        """Override the internal _request method to add logging."""
        import time
        
        request_id = self._get_request_id()
        start_time = time.time()
        
        # Extract and log request details
        headers = kwargs.get('headers', {})
        if hasattr(headers, 'items'):
            headers_dict = dict(headers.items())
        else:
            headers_dict = dict(headers) if headers else {}
            
        # Get request body
        body = None
        if 'data' in kwargs:
            body = kwargs['data']
        elif 'json' in kwargs:
            body = kwargs['json']
        
        # Log the request
        await self.http_logger.log_request(
            method=method.upper(),
            url=str(url),
            headers=headers_dict,
            body=body,
            request_id=request_id
        )
        
        try:
            # Make the actual request
            response = await super()._request(method, url, **kwargs)
            
            # Calculate response time
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Get response headers
            response_headers = dict(response.headers.items()) if response.headers else {}
            
            # Try to read response body for logging (without consuming it)
            response_body = None
            try:
                # Read the response body
                response_body = await response.text()
                
                # Create a new response object with the same data
                # We need to recreate the response because aiohttp responses can only be read once
                from aiohttp.streams import StreamReader
                from aiohttp import ClientResponseError
                import io
                
                # Create new response with the body we just read
                class LoggedResponse(ClientResponse):
                    def __init__(self, original_response, body_text):
                        # Copy attributes from original response
                        self._method = original_response._method
                        self._url = original_response._url
                        self._status = original_response._status
                        self._reason = original_response._reason
                        self._headers = original_response._headers
                        self._history = original_response._history
                        self._request_info = original_response._request_info
                        self._connection = original_response._connection
                        self._closed = original_response._closed
                        self._body_text = body_text
                        self._content = StreamReader(
                            protocol=None, 
                            limit=2**16,
                            loop=asyncio.get_event_loop()
                        )
                        # Feed the body text back into the content stream
                        if body_text:
                            self._content.feed_data(body_text.encode('utf-8'))
                        self._content.feed_eof()

                    async def text(self, encoding='utf-8'):
                        return self._body_text

                    async def json(self, **kwargs):
                        return json.loads(self._body_text) if self._body_text else None

                    async def read(self):
                        return self._body_text.encode('utf-8') if self._body_text else b''

                # Create the logged response
                logged_response = LoggedResponse(response, response_body)
                
                # Log the response
                await self.http_logger.log_response(
                    status=response.status,
                    headers=response_headers,
                    body=response_body,
                    request_id=request_id,
                    response_time_ms=response_time_ms
                )
                
                return logged_response
                
            except Exception as read_error:
                # If we can't read the response body, log without it
                await self.http_logger.log_response(
                    status=response.status,
                    headers=response_headers,
                    body=f"[ERROR READING BODY: {str(read_error)}]",
                    request_id=request_id,
                    response_time_ms=response_time_ms
                )
                return response
                
        except Exception as e:
            # Log error
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self.http_logger.logger.error("=== HTTP Request Failed ===")
            self.http_logger.logger.error(f"Request ID: {request_id}")
            self.http_logger.logger.error(f"Error: {str(e)}")
            self.http_logger.logger.error(f"Response Time: {response_time_ms:.2f}ms")
            self.http_logger.logger.error("=== End Error ===")
            
            raise


def patch_aiohttp_for_logging():
    """Patch aiohttp to use our logging client session globally."""
    import aiohttp
    
    # Store original ClientSession
    original_client_session = aiohttp.ClientSession
    
    # Replace with our logging version
    aiohttp.ClientSession = LoggingClientSession
    
    return original_client_session


def unpatch_aiohttp(original_client_session):
    """Restore original aiohttp ClientSession."""
    import aiohttp
    aiohttp.ClientSession = original_client_session