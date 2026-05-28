# Discord REST API Reference

## Base URL

```
https://discord.com/api/v10
```

## Authentication

### Bot Token (not used here)
```
Authorization: Bot <token>
```

### User Token (what we use)
```
Authorization: <token>
```

User tokens are extracted from the live Discord session via CDP.
No "Bot" prefix needed.

## Thread Endpoints

### List Active Threads
```
GET /channels/{channel_id}/threads/active
```
Returns: `{ threads: [...], members: [...] }`

### List Public Archived Threads
```
GET /channels/{channel_id}/threads/archived/public?limit=100&before=<timestamp>
```
Paginated by `archive_timestamp`. Use `Z` suffix (not `+00:00`).

### List Private Archived Threads
```
GET /channels/{channel_id}/threads/archived/private?limit=100&before=<timestamp>
```
Same pagination as public archived.

### Get Thread Messages
```
GET /channels/{thread_id}/messages?limit=5
```

### Modify Thread (Lock)
```
PATCH /channels/{thread_id}
Body: { "locked": true }
```

### Modify Thread (Archive)
```
PATCH /channels/{thread_id}
Body: { "archived": true }
```

### Send Message
```
POST /channels/{channel_id}/messages
Body: { "content": "Hello" }
```

### Get Current User
```
GET /users/@me
```
Used to verify the extracted token is valid.

## Known Quirks

### 1. Timestamp Format
Discord returns timestamps with `+00:00` but expects `Z` for pagination cursors:
```python
cursor = cursor.replace("+00:00", "Z")
```

### 2. Lock Field Location
The `locked` field appears in `thread_metadata.locked`, NOT at the top level:
```json
{
  "id": "123",
  "locked": null,  // ← unreliable, may be null
  "thread_metadata": {
    "locked": true  // ← this is the real value
  }
}
```

### 3. Lock Before Archive
For reliable behavior, set `locked: true` BEFORE setting `archived: true`:
```python
# Correct order
client.patch(f"/channels/{tid}", json={"locked": True})
time.sleep(0.3)
client.patch(f"/channels/{tid}", json={"archived": True})
```

### 4. Auto-Archived ≠ Locked
Threads that Discord auto-archived are NOT locked. They still need explicit locking.

### 5. User Token Response Differences
Bot tokens and user tokens may return slightly different response structures.
The scripts handle both cases.

## Snowflake Timestamps

Discord IDs are snowflakes that encode creation time:
```python
DISCORD_EPOCH_MS = 1420070400000  # 2015-01-01T00:00:00Z
timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH_MS
dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
```

## Rate Limits

- Discord returns 429 with `Retry-After` header (in seconds)
- Global rate limit: ~50 requests per second
- Per-route rate limits vary
- Always respect `Retry-After` header
- Add delays between batch operations

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 401 | Unauthorized | Token expired, re-extract |
| 403 | Forbidden | Missing permissions |
| 404 | Not Found | Thread was deleted |
| 429 | Rate Limited | Wait and retry |
| 500 | Server Error | Retry with backoff |
