# Discord API Reference for Thread Management

This document covers the Discord REST API endpoints, authentication, pagination,
and known quirks relevant to thread management operations.

## Table of Contents

1. [Authentication](#authentication)
2. [Thread Endpoints](#thread-endpoints)
3. [Pagination](#pagination)
4. [Rate Limiting](#rate-limiting)
5. [Known Quirks & Pitfalls](#known-quirks--pitfalls)
6. [Thread Metadata Fields](#thread-metadata-fields)
7. [Snowflake IDs](#snowflake-ids)

---

## Authentication

Discord API v10 requires an `Authorization` header with either:
- **Bot token**: `Bot <your-bot-token>`
- **User account token**: `<your-user-token>` (no prefix)

```python
# Bot token
headers = {"Authorization": f"Bot {token}"}

# User account token (self-bot — use with caution, see below)
headers = {"Authorization": token}
```

### Token Types and Their Implications

| Aspect | Bot Token | User Account Token |
|--------|-----------|-------------------|
| Authorization prefix | `Bot <token>` | `<token>` (no prefix) |
| Permission source | Bot's role permissions | User's permissions |
| Rate limits | Bot-specific buckets | User-specific buckets |
| `locked` field behavior | Top-level + metadata | May return `None` at top level |
| Risk | Officially supported | Against ToS for automation |

**Important**: Using user account tokens for automation ("self-botting") violates
Discord's Terms of Service and can result in account termination. Use bot tokens
for any automated operations.

---

## Thread Endpoints

### List Active Threads

```
GET /channels/{channel.id}/threads/active
```

Returns all active (non-archived) threads the authenticated user can see.
No pagination — returns all results at once.

**Response**: `{ "threads": [...], "members": [...] }`

### List Public Archived Threads

```
GET /channels/{channel.id}/threads/archived/public
```

Returns public archived threads, paginated.

**Query parameters**:
- `before` (ISO-8601 timestamp): Return threads archived before this time
- `limit` (integer, default 25, max 100): Max threads to return

**Response**: `{ "threads": [...], "members": [...], "has_more": bool }`

### List Private Archived Threads

```
GET /channels/{channel.id}/threads/archived/private
```

Returns private archived threads the user can see, paginated.
Same parameters and response format as public archived.

### Get Thread Messages

```
GET /channels/{channel.id}/messages
```

**Query parameters**:
- `limit` (integer, default 50, max 100): Max messages to return
- `before` (snowflake): Get messages before this ID

### Modify Thread (Lock / Archive)

```
PATCH /channels/{channel.id}
```

**Request body**:
```json
{
  "locked": true,
  "archived": true
}
```

The `locked` field requires `MANAGE_THREADS` permission.
The `archived` field can be set by anyone who can view the thread.

---

## Pagination

### Cursor-Based Pagination for Archived Threads

Discord uses cursor-based pagination for archived thread lists. The cursor is the
`archive_timestamp` of the last thread in the current page.

```python
# Correct pagination pattern
before = None
while True:
    params = {"limit": 100}
    if before:
        params["before"] = before

    resp = requests.get(url, params=params, headers=headers)
    data = resp.json()

    threads = data.get("threads", [])
    if not threads:
        break

    all_threads.extend(threads)

    # Get cursor from last thread
    last = threads[-1]
    cursor = last.get("thread_metadata", {}).get("archive_timestamp", "")
    if cursor:
        before = cursor.replace("+00:00", "Z")  # CRITICAL: see quirks section
    else:
        break

    if not data.get("has_more", False):
        break
```

### Common Pagination Mistakes

1. **Not checking `has_more`**: The API may return fewer threads than `limit`
   even when there are more pages.
2. **Using offset-based pagination**: Discord does not support offset-based
   pagination for thread lists — only cursor-based.
3. **Not normalizing timestamps**: See the `+00:00` vs `Z` quirk below.

---

## Rate Limiting

Discord enforces rate limits on all API endpoints. Key points:

### Rate Limit Headers

- `X-RateLimit-Limit`: Max requests allowed per window
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Epoch time when the rate limit window resets
- `X-RateLimit-Reset-After`: Seconds until the rate limit resets
- `Retry-After`: Seconds to wait (returned with 429 responses)

### Rate Limit Buckets

Discord groups endpoints into "buckets" that share rate limits. Thread modification
endpoints share a bucket, so modifying many threads quickly will trigger rate limits.

### Best Practices

1. **Add delays between requests**: 1-2 seconds between thread modifications
2. **Respect 429 responses**: Parse `Retry-After` and wait that long
3. **Use exponential backoff**: For unexpected errors, increase delay between retries
4. **Don't parallelize modifications**: Sequential processing is safer

```python
# Safe rate-limit handling pattern
def api_request_with_retry(method, url, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        resp = requests.request(method, url, **kwargs)

        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", 1.0))
            time.sleep(retry_after)
            continue

        if resp.status_code >= 500:
            wait = 1.0 * (2 ** attempt)  # 1s, 2s, 4s
            time.sleep(wait)
            continue

        return resp

    return resp  # Return last response after all retries
```

---

## Known Quirks & Pitfalls

### 1. `+00:00` vs `Z` in Timestamps

**Problem**: Discord returns `archive_timestamp` values like `2024-01-15T10:30:00+00:00`,
but when using these as the `before` cursor, Discord expects `2024-01-15T10:30:00Z`.
Using `+00:00` can cause pagination to break (returning empty results or the same page).

**Solution**: Always normalize UTC timestamps to use the `Z` suffix:

```python
cursor = timestamp.replace("+00:00", "Z")
```

### 2. `locked` Field Location

**Problem**: When modifying a thread with `PATCH`, the response may show `locked: None`
at the top level, even when the lock was successfully applied. The actual lock status
is in `thread_metadata.locked`.

**Solution**: Always check `thread_metadata.locked`, not the top-level `locked` field:

```python
resp = client.patch(f"/channels/{thread_id}", json={"locked": True})
data = resp.json()

# WRONG — may be None even when lock succeeded
is_locked = data.get("locked")

# RIGHT — check thread_metadata
is_locked = data.get("thread_metadata", {}).get("locked", False)
```

### 3. Lock Before Archive

**Problem**: If you set `archived: true` before `locked: true` in the same request,
some Discord implementations may not apply the lock because the thread is already
being archived. Or the lock may not persist after the archive operation.

**Solution**: Send lock and archive as separate requests, locking first:

```python
# Step 1: Lock
client.patch(f"/channels/{thread_id}", json={"locked": True})
time.sleep(0.3)

# Step 2: Archive
client.patch(f"/channels/{thread_id}", json={"archived": True})
```

### 4. Auto-Archived Threads Are Already Archived

**Problem**: Discord auto-archives inactive threads after a configured period
(1 hour, 24 hours, 3 days, or 1 week). When you try to archive these threads,
they're already archived — but they're NOT locked.

**Solution**: The archive operation is a no-op (returns 200), but the lock
operation still needs to be applied. Don't skip threads just because they're
already archived.

### 5. Thread Message Counts Can Be Inaccurate

**Problem**: The `message_count` field on thread objects may not include very
recent messages or may be slightly stale.

**Solution**: For critical operations, fetch the actual message count by listing
messages with `GET /channels/{thread_id}/messages?limit=1` and checking the
total count from headers or by paginating.

### 6. Permissions Differ Between Bot and User Tokens

**Problem**: Some operations that work with user tokens don't work the same way
with bot tokens, and vice versa. The `MANAGE_THREADS` permission behaves
differently depending on the token type.

**Solution**: Test your workflow with the actual token type you'll use in
production. Don't assume bot and user tokens have identical behavior.

---

## Thread Metadata Fields

The `thread_metadata` object on thread resources contains:

| Field | Type | Description |
|-------|------|-------------|
| `archived` | bool | Whether the thread is archived |
| `auto_archive_duration` | integer | Auto-archive duration in minutes (60, 1440, 4320, 10080) |
| `archive_timestamp` | ISO-8601 | When the thread's archive status was last changed |
| `locked` | bool | Whether the thread is locked |
| `invitable` | bool | Whether non-moderators can add members (private threads only) |
| `create_timestamp` | ISO-8601 | When the thread was created (may be null for old threads) |

---

## Snowflake IDs

Discord uses snowflake IDs — 64-bit integers that encode creation timestamps.
This is useful for determining when a thread was created without an explicit
`created_at` field.

### Converting Snowflake to Timestamp

```python
DISCORD_EPOCH = 1420070400000  # 2015-01-01T00:00:00.000Z in milliseconds

def snowflake_to_datetime(snowflake: int) -> datetime:
    timestamp_ms = (snowflake >> 22) + DISCORD_EPOCH
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
```

The snowflake structure (64 bits):
- Bits 0-11: Increment within millisecond (12 bits)
- Bits 12-21: Worker/Process ID (5 bits each, 10 total)
- Bits 22-63: Milliseconds since Discord Epoch (42 bits)
