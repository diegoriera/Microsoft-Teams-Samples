# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import json
import asyncio
import time
from typing import Any, Dict, Optional, Union
from aiohttp import ClientSession, ClientResponse
import uuid
import urllib.parse


class SimpleHTTPLogger:
    """Simple HTTP request/response logger."""
    
    def __init__(self, logger_name: str = "HTTPLogger"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)

    def log_request(self, method: str, url: str, headers: Dict[str, Any], 
                   body: Any, request_id: str):
        """Log outgoing HTTP request details with special handling for OAuth requests."""
        # Check if this is an OAuth-related request
        is_oauth_request = self._is_oauth_request(url, headers, body)
        
        sanitized_headers = self._sanitize_headers(headers)
        
        if is_oauth_request:
            self.logger.info("=== OAUTH HTTP REQUEST ===")
        else:
            self.logger.info("=== Outgoing HTTP Request ===")
            
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Method: {method}")
        self.logger.info(f"URL: {url}")
        
        if is_oauth_request:
            self.logger.info("OAuth Request Type: Detected")
            # For OAuth requests, we want to see more header details (but still sanitized)
            self.logger.info(f"Headers (OAuth): {json.dumps(sanitized_headers, indent=2, default=str)}")
        else:
            self.logger.info(f"Headers: {json.dumps(sanitized_headers, indent=2, default=str)}")
        
        if body is not None:
            body_logged = False
            
            # Special handling for OAuth body content
            if is_oauth_request:
                self.logger.info("OAuth Body Content:")
                
            try:
                if isinstance(body, (str, bytes)):
                    if isinstance(body, bytes):
                        body_str = body.decode('utf-8', errors='ignore')
                    else:
                        body_str = body
                    
                    # Try to parse as JSON for pretty printing
                    try:
                        json_body = json.loads(body_str)
                        if is_oauth_request:
                            # For OAuth, log with special formatting
                            self.logger.info(f"Body (OAuth JSON): {json.dumps(json_body, indent=2, default=str)}")
                        else:
                            self.logger.info(f"Body: {json.dumps(json_body, indent=2, default=str)}")
                        body_logged = True
                    except json.JSONDecodeError:
                        # Handle URL-encoded OAuth data (common for token requests)
                        if is_oauth_request and ('grant_type' in body_str or 'client_id' in body_str):
                            self.logger.info(f"Body (OAuth URL-encoded): {body_str}")
                        else:
                            self.logger.info(f"Body (raw): {body_str}")
                        body_logged = True
                elif isinstance(body, dict):
                    # Handle dict bodies (common with aiohttp json parameter)
                    if is_oauth_request:
                        self.logger.info(f"Body (OAuth Dict): {json.dumps(body, indent=2, default=str)}")
                    else:
                        self.logger.info(f"Body: {json.dumps(body, indent=2, default=str)}")
                    body_logged = True
                else:
                    # Handle other body types
                    if is_oauth_request:
                        self.logger.info(f"Body (OAuth Other): {json.dumps(body, indent=2, default=str)}")
                    else:
                        self.logger.info(f"Body: {json.dumps(body, indent=2, default=str)}")
                    body_logged = True
                    
            except Exception as e:
                self.logger.info(f"Body (error parsing): {str(body)}")
                body_logged = True
                
            if not body_logged:
                self.logger.info(f"Body (fallback): {str(body)}")
        else:
            self.logger.info("Body: (empty)")
        
        if is_oauth_request:
            self.logger.info("=== END OAUTH REQUEST ===")
        else:
            self.logger.info("=== End Request ===")

    def log_response(self, status: int, headers: Dict[str, Any], 
                    body: Optional[str], request_id: str, 
                    response_time_ms: float, is_oauth_response: bool = False):
        """Log HTTP response details with special handling for OAuth responses."""
        sanitized_headers = self._sanitize_headers(headers)
        
        if is_oauth_response:
            self.logger.info("=== OAUTH HTTP RESPONSE ===")
        else:
            self.logger.info("=== HTTP Response ===")
            
        self.logger.info(f"Request ID: {request_id}")
        self.logger.info(f"Status Code: {status}")
        self.logger.info(f"Response Time: {response_time_ms:.2f}ms")
        
        if is_oauth_response:
            self.logger.info(f"Headers (OAuth): {json.dumps(sanitized_headers, indent=2, default=str)}")
        else:
            self.logger.info(f"Headers: {json.dumps(sanitized_headers, indent=2, default=str)}")
        
        if body:
            try:
                # Try to parse as JSON for pretty printing
                json_body = json.loads(body)
                if is_oauth_response:
                    self.logger.info(f"Body (OAuth JSON): {json.dumps(json_body, indent=2, default=str)}")
                else:
                    self.logger.info(f"Body: {json.dumps(json_body, indent=2, default=str)}")
            except json.JSONDecodeError:
                if is_oauth_response:
                    self.logger.info(f"Body (OAuth raw): {body}")
                else:
                    self.logger.info(f"Body (raw): {body}")
        else:
            self.logger.info("Body: (empty)")
            
        if is_oauth_response:
            self.logger.info("=== END OAUTH RESPONSE ===")
        else:
            self.logger.info("=== End Response ===")

    def log_error(self, request_id: str, error: str, response_time_ms: float):
        """Log HTTP request error."""
        self.logger.error("=== HTTP Request Failed ===")
        self.logger.error(f"Request ID: {request_id}")
        self.logger.error(f"Error: {error}")
        self.logger.error(f"Response Time: {response_time_ms:.2f}ms")
        self.logger.error("=== End Error ===")
    
    def is_oauth_request(self, url: str, headers: Dict[str, Any], body: Any) -> bool:
        """Public wrapper for OAuth request detection."""
        return self._is_oauth_request(url, headers, body)

    def _is_oauth_request(self, url: str, headers: Dict[str, Any], body: Any) -> bool:
        """Detect if this is an OAuth-related request."""
        url_lower = url.lower()
        
        # Check URL patterns for OAuth endpoints
        oauth_url_patterns = [
            '/oauth',
            '/token',
            '/auth',
            '/login',
            'login.microsoftonline.com',
            'api.botframework.com',
            'graph.microsoft.com',
            '/v2.0/token',
            '/common/oauth2'
        ]
        
        if any(pattern in url_lower for pattern in oauth_url_patterns):
            return True
            
        # Check headers for OAuth-related content
        for key, value in headers.items():
            if key.lower() == 'authorization' and value and 'bearer' in str(value).lower():
                return True
                
        # Check body content for OAuth parameters
        if body:
            body_str = str(body).lower()
            oauth_body_patterns = [
                'grant_type',
                'client_id',
                'client_secret',
                'access_token',
                'refresh_token',
                'authorization_code',
                'client_credentials'
            ]
            if any(pattern in body_str for pattern in oauth_body_patterns):
                return True
                
        return False

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
            elif any(sensitive in key_lower for sensitive in ['token', 'secret', 'password', 'key']):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized


# Global logger instance
_http_logger = SimpleHTTPLogger("OutgoingHTTP")

# Store original methods for restoration
_original_request = None


async def _logged_request(self, method: str, url, **kwargs):
    """Wrapper around ClientSession._request with logging."""
    request_id = f"req_{uuid.uuid4().hex[:8]}"
    start_time = time.time()
    
    try:
        # Extract request details for logging
        headers = kwargs.get('headers', {})
        if headers and hasattr(headers, 'items'):
            headers_dict = dict(headers.items())
        else:
            headers_dict = dict(headers) if headers else {}
            
        # Get request body
        body = kwargs.get('data') or kwargs.get('json')
        
        # Check if this is an OAuth request
        is_oauth = _http_logger._is_oauth_request(str(url), headers_dict, body)
        
        # Log the request
        _http_logger.log_request(
            method=method.upper(),
            url=str(url),
            headers=headers_dict,
            body=body,
            request_id=request_id
        )
        
        # Make the actual request using the original method
        response = await _original_request(self, method, url, **kwargs)
        
        # Calculate response time
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        # Get response headers
        response_headers = dict(response.headers.items()) if response.headers else {}
        
        # For OAuth requests, try to capture response body safely
        response_body = "[Response body not captured to prevent consumption issues]"
        if is_oauth:
            try:
                # For OAuth responses, try to peek at the response
                response_body = "[OAuth Response - attempting to capture body]"
                # Note: In a real implementation, you might want to capture the body
                # but this requires careful handling to avoid consuming the response stream
            except Exception:
                response_body = "[OAuth Response - body capture failed]"
        
        # Log response with OAuth detection
        _http_logger.log_response(
            status=response.status,
            headers=response_headers,
            body=response_body,
            request_id=request_id,
            response_time_ms=response_time_ms,
            is_oauth_response=is_oauth
        )
        
        return response
        
    except Exception as e:
        # Log error
        end_time = time.time()
        response_time_ms = (end_time - start_time) * 1000
        
        _http_logger.log_error(
            request_id=request_id,
            error=str(e),
            response_time_ms=response_time_ms
        )
        
        raise


# Global variables to store original methods from other libraries
_original_requests_request = None
_original_urllib3_urlopen = None
_original_msal_send_request = None


def _patch_requests_library():
    """Patch the requests library to log HTTP requests."""
    global _original_requests_request
    
    try:
        import requests
        import requests.adapters
        
        if _original_requests_request is not None:
            return  # Already patched
        
        # Store original request method
        _original_requests_request = requests.adapters.HTTPAdapter.send
        
        def logged_requests_send(self, request, **kwargs):
            """Logged version of requests HTTPAdapter.send."""
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            start_time = time.time()
            
            # Log request
            _http_logger.log_request(
                method=request.method,
                url=request.url,
                headers=dict(request.headers) if request.headers else {},
                body=request.body,
                request_id=request_id
            )
            
            try:
                # Call original method
                response = _original_requests_request(self, request, **kwargs)
                
                # Log response
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                _http_logger.log_response(
                    status=response.status_code,
                    headers=dict(response.headers) if response.headers else {},
                    body=None,  # Don't capture response body to avoid consumption issues
                    request_id=request_id,
                    response_time_ms=response_time_ms,
                    is_oauth_response=_http_logger.is_oauth_request(request.url, dict(request.headers) if request.headers else {}, request.body)
                )
                
                return response
                
            except Exception as e:
                # Log error
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                _http_logger.log_error(
                    request_id=request_id,
                    error=str(e),
                    response_time_ms=response_time_ms
                )
                raise
        
        # Apply patch
        requests.adapters.HTTPAdapter.send = logged_requests_send
        
    except ImportError:
        # requests library not available
        pass


def _patch_urllib3_library():
    """Patch urllib3 library to log HTTP requests."""
    global _original_urllib3_urlopen
    
    try:
        import urllib3
        
        if _original_urllib3_urlopen is not None:
            return  # Already patched
        
        # Store original urlopen method
        _original_urllib3_urlopen = urllib3.poolmanager.PoolManager.urlopen
        
        def logged_urllib3_urlopen(self, method, url, **kwargs):
            """Logged version of urllib3 PoolManager.urlopen."""
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            start_time = time.time()
            
            # Extract headers and body from kwargs
            headers = kwargs.get('headers', {})
            body = kwargs.get('body')
            
            # Log request
            _http_logger.log_request(
                method=method,
                url=url,
                headers=dict(headers) if headers else {},
                body=body,
                request_id=request_id
            )
            
            try:
                # Call original method
                response = _original_urllib3_urlopen(self, method, url, **kwargs)
                
                # Log response
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                _http_logger.log_response(
                    status=response.status,
                    headers=dict(response.headers) if hasattr(response, 'headers') else {},
                    body=None,  # Don't capture response body to avoid consumption issues
                    request_id=request_id,
                    response_time_ms=response_time_ms,
                    is_oauth_response=_http_logger.is_oauth_request(url, headers or {}, body)
                )
                
                return response
                
            except Exception as e:
                # Log error
                end_time = time.time()
                response_time_ms = (end_time - start_time) * 1000
                
                _http_logger.log_error(
                    request_id=request_id,
                    error=str(e),
                    response_time_ms=response_time_ms
                )
                raise
        
        # Apply patch
        urllib3.poolmanager.PoolManager.urlopen = logged_urllib3_urlopen
        
    except ImportError:
        # urllib3 library not available
        pass


def _patch_msal_library():
    """Patch MSAL library to log OAuth requests."""
    global _original_msal_send_request
    
    try:
        # MSAL uses requests internally, so if we patch requests, we'll catch MSAL too
        # But let's also try to patch MSAL directly if possible
        import msal
        
        if _original_msal_send_request is not None:
            return  # Already patched
        
        # MSAL typically uses requests.Session internally
        # Since we're already patching requests, MSAL calls should be caught
        # This is a placeholder for direct MSAL patching if needed in future
        
    except (ImportError, AttributeError):
        # MSAL library not available or structure different
        pass


def enable_http_logging():
    """Enable HTTP request/response logging by patching multiple HTTP libraries."""
    global _original_request
    
    if _original_request is not None:
        # Already patched
        return
    
    # Patch aiohttp (async HTTP client)
    _original_request = ClientSession._request
    ClientSession._request = _logged_request
    
    # Patch requests library (synchronous HTTP client)
    _patch_requests_library()
    
    # Patch urllib3 (low-level HTTP library)
    _patch_urllib3_library()
    
    # Patch msal library (Microsoft Authentication Library)
    _patch_msal_library()
    
    _http_logger.logger.info("HTTP request/response logging enabled for multiple libraries")


def disable_http_logging():
    """Disable HTTP request/response logging by restoring original methods."""
    global _original_request, _original_requests_request, _original_urllib3_urlopen, _original_msal_send_request
    
    if _original_request is None:
        # Not patched
        return
    
    # Restore aiohttp
    ClientSession._request = _original_request
    _original_request = None
    
    # Restore requests library
    if _original_requests_request is not None:
        try:
            import requests.adapters
            requests.adapters.HTTPAdapter.send = _original_requests_request
            _original_requests_request = None
        except ImportError:
            pass
    
    # Restore urllib3
    if _original_urllib3_urlopen is not None:
        try:
            import urllib3.poolmanager
            urllib3.poolmanager.PoolManager.urlopen = _original_urllib3_urlopen
            _original_urllib3_urlopen = None
        except ImportError:
            pass
    
    _http_logger.logger.info("HTTP request/response logging disabled for all libraries")