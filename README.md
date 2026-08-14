# LinkPlease Tech Intern — Assignment

A webhook-driven DM automation service built on top of the PseudoGram mock API.

## What this does

When someone comments a keyword (e.g. `PRICE`) on an Instagram post, this service automatically sends them a DM with a predefined message. It handles all the real-world chaos of platform APIs: duplicate events, random failures, rate limits, and silent delivery failures.

## Quick start

```bash
# 1. Clone & install
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env → set PSEUDOGRAM_API_KEY

# 3. Run
uvicorn app.main:app --reload --port 8000
```

## API endpoints

### `POST /rules` — Create a rule
```json
// Request
{ "keyword": "PRICE", "dm_message": "Here's the price list: ..." }

// Response 201
{ "rule_id": "rule_a1b2c3d4e5f6", "keyword": "PRICE", "dm_message": "..." }
```

### `POST /webhook` — Receive comment events
PseudoGram POSTs comment events here. Returns `200` immediately; processing happens in the background.

### `GET /stats` — Live statistics
```json
{
  "sent": 142,
  "failed": 3,
  "queued": 8,
  "duplicates_blocked": 57
}
```

## Architecture

```
POST /webhook → asyncio.Queue → EventProcessor → DB (dm_tasks)
                                                       ↓
                                                  DMSender (background loop)
                                                       ↓
                                              POST /v1/dm/send (rate-limited)
                                                       ↓
                                                  Reconciler (background loop)
                                                       ↓
                                              GET /v1/dm/{id} (free reads)
```

## Parts completed

- **Part A**: Rule creation, keyword matching, user-rule deduplication, retry on failure
- **Part B**: HMAC-SHA256 webhook signature verification
- **Part C**: Delivery reconciliation, `comment.deleted` handling, burst handling

## Stack

- Python 3.11+ / FastAPI
- SQLite (WAL mode) for persistence
- httpx (async) for API calls
- aiosqlite for non-blocking DB access
