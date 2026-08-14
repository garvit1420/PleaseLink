"""
Webhook event processor — runs as a single background consumer.

Events arrive via an asyncio.Queue so the /webhook endpoint
returns 200 instantly while processing happens here.

Handles:
  • event_id deduplication  (~8 % of events are redelivered)
  • comment.created → keyword matching → DM task creation
  • comment.deleted → cancel pending DMs (Part C)
  • out-of-order deletions (deletion arrives before creation)
  • user-rule deduplication (same user + same rule = one DM, ever)
"""

import asyncio
import json
import logging

from app.database import Database

logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(self, db: Database):
        self.db = db
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._running = True

    # ── Public API ──────────────────────────────────────────────

    async def enqueue(self, raw_body: bytes):
        """Called from the webhook endpoint — non-blocking."""
        await self.queue.put(raw_body)

    async def run(self):
        """Main loop — consumes events from the queue one at a time."""
        logger.info("Event processor started")
        while self._running:
            try:
                raw_body = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            try:
                await self._process(raw_body)
            except Exception:
                logger.exception("Failed to process event")

    def stop(self):
        self._running = False

    # ── Internal ────────────────────────────────────────────────

    async def _process(self, raw_body: bytes):
        event = json.loads(raw_body)
        event_id = event.get("event_id")
        event_type = event.get("event_type")
        data = event.get("data", {})

        if not event_id:
            logger.warning("Event missing event_id, skipping")
            return

        # ── Event-level dedup ───────────────────────────────────
        if await self.db.is_event_processed(event_id):
            logger.debug("Duplicate event %s — skipped", event_id)
            return

        await self.db.mark_event_processed(event_id)

        # ── Route by type ───────────────────────────────────────
        if event_type == "comment.deleted":
            await self._handle_deleted(data)
        elif event_type == "comment.created":
            await self._handle_comment(data)
        else:
            logger.warning("Unknown event type: %s", event_type)

    async def _handle_deleted(self, data: dict):
        """
        Cancel any pending DMs for this comment.
        Also store the deletion so that if the matching comment.created
        arrives later (out of order), we won't create a DM for it.
        """
        comment_id = data.get("comment_id")
        if not comment_id:
            return

        await self.db.mark_comment_deleted(comment_id)
        cancelled = await self.db.cancel_pending_dms_for_comment(comment_id)
        if cancelled:
            logger.info("comment.deleted %s — cancelled %d pending DMs", comment_id, cancelled)

    async def _handle_comment(self, data: dict):
        """Match the comment text against every rule and queue DMs."""
        comment_id = data.get("comment_id")
        text = data.get("text", "")
        from_data = data.get("from", {})
        user_id = from_data.get("user_id")

        if not comment_id or not user_id:
            logger.warning("Comment missing comment_id or user_id")
            return

        # If the comment was already deleted (deletion arrived first), skip
        if await self.db.is_comment_deleted(comment_id):
            logger.info("Comment %s already deleted — skipping", comment_id)
            return

        # Fetch rules and match
        rules = await self.db.get_all_rules()
        text_lower = text.lower()

        for rule in rules:
            keyword_lower = rule["keyword"].lower()

            if keyword_lower not in text_lower:
                continue

            # Deterministic idempotency key: same user + same rule = same key
            idempotency_key = f"{user_id}-{rule['id']}"

            created = await self.db.create_dm_task(
                rule_id=rule["id"],
                user_id=user_id,
                comment_id=comment_id,
                dm_message=rule["dm_message"],
                idempotency_key=idempotency_key,
            )

            if created:
                logger.info(
                    "Queued DM: user=%s rule=%s comment=%s",
                    user_id, rule["id"], comment_id,
                )
            else:
                # (user_id, rule_id) already exists → legitimate duplicate
                await self.db.increment_duplicates_blocked()
                logger.info(
                    "Duplicate blocked: user=%s rule=%s",
                    user_id, rule["id"],
                )
