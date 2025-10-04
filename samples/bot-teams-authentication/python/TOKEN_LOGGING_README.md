# HTTP Request Logging Implementation

This document explains the HTTP request logging implementation added to the Microsoft Teams authentication bot.

## Overview

The HTTP logging functionality captures all outgoing HTTP requests made by the bot application, including:
- Request method, URL, headers, and body
- Response status code, headers, and timing
- Error details for failed requests
- Automatic sanitization of sensitive headers

## Files Added

### 1. `simple_http_logger.py`
The main HTTP logging implementation that:
- Patches aiohttp's `ClientSession._request` method
- Logs all outgoing HTTP requests and responses
- Sanitizes sensitive headers (Authorization, API keys, tokens, etc.)
- Provides enable/disable functionality

### 2. `http_logger.py` 
A more complex implementation with response body capture (kept for reference but not used due to response consumption issues)

### 3. `test_http_logging.py`
Test script to verify the HTTP logging functionality with various request types

### 4. `TOKEN_LOGGING_README.md`
This documentation file

## Usage

The HTTP logging is automatically enabled when the application starts. It's activated in `app.py`:

```python
from simple_http_logger import enable_http_logging

# Enable HTTP request/response logging for all outgoing HTTP calls
enable_http_logging()
```

## Log Format

### Request Logs
```
=== Outgoing HTTP Request ===
Request ID: req_a1b2c3d4
Method: POST
URL: https://api.example.com/oauth/token
Headers: {
  "Content-Type": "application/json",
  "User-Agent": "BotFramework/4.17.0",
  "Authorization": "[REDACTED]"
}
Body: {
  "grant_type": "client_credentials",
  "scope": "https://graph.microsoft.com/.default"
}
=== End Request ===
```

### Response Logs
```
=== HTTP Response ===
Request ID: req_a1b2c3d4
Status Code: 200
Response Time: 245.67ms
Headers: {
  "Content-Type": "application/json",
  "Cache-Control": "no-store"
}
Body: [Response body not captured to prevent consumption issues]
=== End Response ===
```

### Error Logs
```
=== HTTP Request Failed ===
Request ID: req_a1b2c3d4
Error: Connection timeout
Response Time: 5000.00ms
=== End Error ===
```

## Security Features

### Header Sanitization
Sensitive headers are automatically redacted in logs:
- `Authorization`
- `X-API-Key`
- `Cookie` / `Set-Cookie`
- Any header containing: `token`, `secret`, `password`, `key`

Example:
```json
{
  "Authorization": "[REDACTED]",
  "X-API-Key": "[REDACTED]",
  "Content-Type": "application/json"
}
```

### Body Logging
- JSON bodies are pretty-printed for readability
- Raw text bodies are logged as-is
- Binary bodies are converted to string representation
- No sensitive data filtering is applied to bodies (consider adding if needed)

## Implementation Details

### Monkey Patching Approach
The implementation uses monkey patching to intercept all HTTP requests:

1. Stores the original `aiohttp.ClientSession._request` method
2. Replaces it with a logging wrapper
3. The wrapper logs request details, calls the original method, then logs the response
4. Can be disabled to restore original behavior

### Request ID Generation
Each request gets a unique ID (`req_xxxxxxxx`) for correlating request and response logs.

### Timing Information
Response time is measured from request start to response completion.

### Error Handling
- Exceptions during logging don't break the original request
- Failed requests are logged with error details
- Network timeouts and connection errors are captured

## Bot Framework Integration

This logging captures HTTP requests made by:
- Bot Connector API calls
- Microsoft Graph API requests
- OAuth token requests
- Any custom HTTP requests made by bot code

## Testing

Run the test script to verify logging functionality:

```bash
python test_http_logging.py
```

This will make various HTTP requests and show the logging output.

## Configuration Options

### Enable/Disable Logging
```python
from simple_http_logger import enable_http_logging, disable_http_logging

# Enable logging
enable_http_logging()

# Disable logging
disable_http_logging()
```

### Logger Configuration
The HTTP logger uses Python's standard logging module with logger name `OutgoingHTTP`. You can configure it like any other logger:

```python
import logging

# Set log level
logging.getLogger('OutgoingHTTP').setLevel(logging.DEBUG)

# Add custom handler
handler = logging.FileHandler('http_requests.log')
logging.getLogger('OutgoingHTTP').addHandler(handler)
```

## Performance Considerations

### Minimal Overhead
- Logging adds minimal overhead to HTTP requests
- Request/response data is processed asynchronously
- No blocking operations in the logging path

### Memory Usage
- Request/response data is not stored long-term
- JSON parsing is done only for logging formatting
- Large response bodies are handled efficiently

### Response Body Capture
The current implementation doesn't capture response bodies to avoid:
- Consuming the response stream (which would break the original request)
- Memory issues with large responses
- Potential issues with binary content

## Troubleshooting

### Logging Not Appearing
1. Check if `enable_http_logging()` was called
2. Verify logging configuration (level, handlers)
3. Ensure the logger name `OutgoingHTTP` is not filtered out

### Performance Issues
1. Consider disabling logging in production if not needed
2. Adjust log levels (use WARNING or ERROR instead of INFO)
3. Use asynchronous log handlers for high-traffic scenarios

### Missing Requests
- The logging only captures requests made through aiohttp
- Requests made through other HTTP clients won't be logged
- Synchronous requests (if any) won't be captured

## Future Enhancements

### Potential Improvements
1. **Response Body Capture**: Implement safe response body capture without consuming the stream
2. **Request Filtering**: Add configuration to filter out certain URLs or request types
3. **Structured Logging**: Use structured logging formats (JSON) for better parsing
4. **Rate Limiting**: Add rate limiting for high-frequency requests
5. **Async Logging**: Use async logging handlers to reduce impact on request performance
6. **Body Sanitization**: Add body-level sensitive data filtering

### Configuration File Support
Consider adding a configuration file for:
- Enabling/disabling logging
- Setting log levels
- Configuring sensitive header patterns
- Request filtering rules

## Integration with Monitoring Systems

The logged data can be integrated with:
- Application Insights (Azure)
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Prometheus/Grafana
- Custom monitoring solutions

Example structured logging format:
```json
{
  "timestamp": "2023-XX-XX...",
  "request_id": "req_a1b2c3d4",
  "method": "POST",
  "url": "https://api.example.com/...",
  "status_code": 200,
  "response_time_ms": 245.67,
  "headers": {...},
  "body_size": 1234
}
```

This implementation provides comprehensive HTTP request logging for debugging, monitoring, and auditing purposes while maintaining security best practices.
