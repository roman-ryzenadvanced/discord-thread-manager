# Chrome DevTools Protocol (CDP) Reference

## Overview

Discord Desktop is built on Electron (Chromium). When launched with
`--remote-debugging-port=9222`, it exposes the Chrome DevTools Protocol,
allowing external tools to:

- Inspect and manipulate the DOM
- Execute JavaScript in the renderer context
- Read localStorage, cookies, and session data
- Intercept network requests

## Connecting

### CDP HTTP Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET http://127.0.0.1:9222/json` | List all debuggable targets |
| `GET http://127.0.0.1:9222/json/version` | Browser version info |

### Target Discovery

```json
[
  {
    "description": "",
    "devtoolsFrontendUrl": "...",
    "id": "...",
    "title": "Discord",
    "type": "page",
    "url": "https://discord.com/channels/...",
    "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/..."
  }
]
```

Use the `webSocketDebuggerUrl` to connect via WebSocket.

### WebSocket Connection

```python
import websocket
ws = websocket.create_connection(ws_url, timeout=10)
```

## Runtime.evaluate

Execute JavaScript in the renderer context:

```json
{
  "id": 1,
  "method": "Runtime.evaluate",
  "params": {
    "expression": "document.title",
    "returnByValue": true,
    "awaitPromise": false
  }
}
```

Response:
```json
{
  "id": 1,
  "result": {
    "result": {
      "type": "string",
      "value": "Discord"
    }
  }
}
```

## Token Extraction Methods

### Method 1: localStorage

Discord may store the auth token in localStorage:

```javascript
localStorage.getItem('token')
// Returns: "\"MTIzNDU2Nzg5...\"" (quoted string)
```

Strip the surrounding quotes:
```python
token = token.strip('"').strip("'")
```

### Method 2: Script Tag Parsing

Some Discord builds embed the token in initial page scripts:

```javascript
var scripts = document.querySelectorAll('script');
for (var i = 0; i < scripts.length; i++) {
    var match = scripts[i].textContent.match(/"token"\s*:\s*"([^"]{30,})"/);
    if (match) return match[1];
}
```

### Method 3: Webpack Module Cache

Discord uses webpack. The module cache sometimes exposes a `getToken()` function:

```javascript
// Search through webpackChunkdiscord_app loaded modules
var cache = window.webpackChunkdiscord_app;
// ... iterate to find module with getToken() export
```

## DOM Manipulation

### Click an element
```javascript
document.querySelector('[aria-label="Thread Menu"]').click()
```

### Type into an element
```javascript
var el = document.querySelector('[contenteditable="true"]');
el.focus();
el.textContent = "Hello";
el.dispatchEvent(new Event('input', {bubbles: true}));
```

### Read element text
```javascript
document.querySelector('.thread-title').textContent
```

## Security Considerations

- **CDP has full access** to the renderer — treat it like root access to the page
- **No authentication** on the CDP port — only use on localhost
- **Port 9222** should never be exposed to the network
- **Close the connection** when done to avoid resource leaks

## Rate Limiting

CDP itself doesn't have rate limits, but:
- Rapid DOM manipulation can freeze the Discord UI
- Add small delays (100-300ms) between DOM operations
- Discord's internal reactivity system may batch updates

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CDP endpoint not responding | Discord not launched with `--remote-debugging-port` |
| No targets found | Wait for Discord to fully load |
| WebSocket connection refused | Check if port 9222 is already in use |
| JS evaluation returns undefined | Check the expression syntax, try in Chrome DevTools first |
| Token extraction returns null | User might not be logged in, or Discord build changed |
