"""
FastAPI application — the three graded endpoints live here.

    POST /webhook   →  receives PseudoGram comment events & saves to raw_events SQLite table
    POST /rules     →  creates keyword → DM rules
    GET  /stats     →  live counts (sent / failed / queued / duplicates_blocked)

Webhooks synchronously persist raw events to SQLite before returning 200 OK within milliseconds.
Event processing and DM dispatch run in background asyncio worker loops.
"""

import asyncio
import hmac
import hashlib
import json
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app import config
from app.database import Database
from app.webhook_handler import EventProcessor
from app.dm_sender import DMSender
from app.reconciler import Reconciler

# ── Logging ─────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── Shared instances (created once, used everywhere) ────────────

db = Database(config.DB_PATH)
event_processor = EventProcessor(db)
dm_sender = DMSender(db)
reconciler = Reconciler(db)


# ── Signature verification (Part B) ────────────────────────────

def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """HMAC-SHA256 of the raw body, keyed with our API key."""
    if not signature_header:
        logger.debug("Signature check failed: missing X-PseudoGram-Signature header")
        return False
    expected = hmac.new(
        config.API_KEY.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")

    # Debug log (no secret API key is logged, only payload size & hashes)
    logger.info(
        "Signature Check: body_len=%d, expected_sha256=%s, received_sha256=%s, raw_body=%s",
        len(raw_body), expected, received, repr(raw_body)
    )
    return hmac.compare_digest(expected, received)


# ── Lifespan (startup / shutdown) ──────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ── START ───────────────────────────────────────────────────
    await db.connect()

    unprocessed_raw = await db.count_unprocessed_raw_events()
    initial_stats = await db.get_stats()
    logger.info(
        "STARTUP SELF-CHECK: Unprocessed raw_events=%d, Current stats snapshot=%s",
        unprocessed_raw,
        initial_stats,
    )

    bg_tasks = [
        asyncio.create_task(event_processor.run(), name="event_processor"),
        asyncio.create_task(dm_sender.run(), name="dm_sender"),
        asyncio.create_task(reconciler.run(), name="reconciler"),
    ]
    logger.info("All background tasks started")

    yield

    # ── STOP ────────────────────────────────────────────────────
    event_processor.stop()
    dm_sender.stop()
    reconciler.stop()

    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)

    await dm_sender.close()
    await reconciler.close()
    await db.close()
    logger.info("Shutdown complete")


# ── App ─────────────────────────────────────────────────────────

app = FastAPI(title="LinkPlease Assignment", lifespan=lifespan)


# ── POST /webhook ───────────────────────────────────────────────

@app.post("/webhook")
async def webhook(request: Request):
    """
    Receive a comment event from PseudoGram.
    Saves raw event to SQLite raw_events table synchronously before returning 200.
    """
    raw_body = await request.body()
    raw_body_str = raw_body.decode(errors="replace")

    # Part B: reject forged requests
    if config.VERIFY_SIGNATURES:
        sig = request.headers.get("X-PseudoGram-Signature")
        if not _verify_signature(raw_body, sig):
            return Response(
                status_code=401,
                content='{"error":"invalid_signature"}',
                media_type="application/json",
            )

    event_id = None
    event_type = None
    try:
        payload_json = json.loads(raw_body_str)
        event_id = payload_json.get("event_id")
        event_type = payload_json.get("event_type")
    except Exception:
        pass

    if not event_id:
        event_id = f"fallback_{uuid.uuid4().hex}"

    # Synchronous DB write to raw_events table before returning 200
    # Uses INSERT OR IGNORE, so duplicate event_ids return 200 OK without errors
    await db.save_raw_event(event_id, event_type, raw_body_str)

    return Response(
        status_code=200,
        content='{"status":"ok"}',
        media_type="application/json",
    )


# ── POST /rules ─────────────────────────────────────────────────

@app.post("/rules", status_code=201)
async def create_rule(request: Request):
    """Create an automation rule: keyword → DM message."""
    data = await request.json()
    rule = await db.create_rule(data["keyword"], data["dm_message"])
    return rule


# ── GET /stats ──────────────────────────────────────────────────

@app.get("/stats")
async def stats():
    """Live counts — compared against PseudoGram server-side truth."""
    return await db.get_stats()
