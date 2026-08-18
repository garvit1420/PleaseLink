"""
Background DM sender — pulls tasks from the queue and sends them
via the PseudoGram mock API, respecting the rate limit.

Key behaviours:
  • Sliding-window rate limiter  (9 req / 60 s — safety margin below the 10-limit)
  • Idempotency-Key header       (safe retries — PseudoGram deduplicates on the key)
  • Exponential backoff on 500   (1 s → 2 s → 4 s → 8 s → 16 s, then give up)
  • Respect Retry-After on 429   (pause the entire sender, not just one task)
  • Never retry on 400           (malformed payload — retrying won't help)
"""

import asyncio
import time
import logging

import httpx

from app.database import Database
from app import config

logger = logging.getLogger(__name__)


# ── Rate limiter ────────────────────────────────────────────────

class SlidingWindowRateLimiter:
    """
    Allows at most `max_requests` calls within a rolling `window` seconds.

    We use 9 (not 10) to leave headroom; network timing
    jitter can push us over if we cut it exactly at 10.
    """

    def __init__(self, max_requests: int = 9, window: int = 60):
        self.max_requests = max_requests
        self.window = window
        self._timestamps: list[float] = []

    async def acquire(self):
        """Block until a slot is available, then consume it."""
        while True:
            now = time.time()
            # Purge expired timestamps
            self._timestamps = [t for t in self._timestamps if now - t < self.window]

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return

            # Wait until the oldest slot expires
            wait = self.window - (now - self._timestamps[0]) + 0.5
            logger.debug("Rate limiter: waiting %.1fs", wait)
            await asyncio.sleep(wait)

    def release_last(self):
        """Undo the last acquire (used when the server returns 429)."""
        if self._timestamps:
            self._timestamps.pop()


# ── DM Sender ──────────────────────────────────────────────────

class DMSender:
    def __init__(self, db: Database):
        self.db = db
        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests=config.RATE_LIMIT_MAX,
            window=config.RATE_LIMIT_WINDOW,
        )
        self.client = httpx.AsyncClient(
            base_url=config.BASE_URL,
            headers={
                "X-API-Key": config.API_KEY,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
        self._running = True

    # ── Lifecycle ───────────────────────────────────────────────

    async def run(self):
        logger.info("DM sender started")
        while self._running:
            try:
                task = await self.db.get_next_queued_task()
                if task is None:
                    await asyncio.sleep(config.SENDER_POLL_INTERVAL)
                    continue
                await self._send(task)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("DM sender loop error")
                await asyncio.sleep(1)

    def stop(self):
        self._running = False

    async def close(self):
        await self.client.aclose()

    # ── Send one DM ─────────────────────────────────────────────

    async def _send(self, task: dict):
        task_id = task["id"]
        retry_count = task["retry_count"]

        # Mark as sending so no other worker picks it up
        await self.db.update_task_sending(task_id)

        # Wait for a rate-limit slot
        await self.rate_limiter.acquire()

        # Idempotency key per attempt: task_key-v{retry_count}
        idempotency_key = f"{task['idempotency_key']}-v{retry_count}"

        try:
            resp = await self.client.post(
                "/v1/dm/send",
                json={
                    "recipient_user_id": task["user_id"],
                    "message": task["dm_message"],
                    "comment_id": task["comment_id"],
                },
                headers={"Idempotency-Key": idempotency_key},
            )
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            # Network or timeout error — retry
            logger.error("Network/Timeout error sending DM (task %d): %s", task_id, exc)
            await self._schedule_retry(task_id, retry_count)
            return

        # ── 200/202 Accepted ────────────────────────────────────
        if resp.status_code in (200, 202):
            dm_id = resp.json().get("dm_id", "")
            await self.db.update_task_accepted(task_id, dm_id)
            logger.info("DM accepted: task=%d dm_id=%s", task_id, dm_id)
            return

        # ── 429 Rate Limited ────────────────────────────────────
        if resp.status_code == 429:
            self.rate_limiter.release_last()
            retry_after = int(resp.headers.get("Retry-After", "10"))
            # Put the task back and pause the ENTIRE sender
            next_at = time.time() + retry_after
            await self.db.update_task_retry(task_id, retry_count, next_at)
            logger.warning("429 rate-limited — pausing sender for %ds", retry_after)
            await asyncio.sleep(retry_after)
            return

        # ── 500 Internal Error (safe to retry) ──────────────────
        if resp.status_code == 500:
            logger.warning("500 from API (task %d), retry %d/%d", task_id, retry_count + 1, config.MAX_RETRIES)
            await self._schedule_retry(task_id, retry_count)
            return

        # ── 400 Bad Request (permanent failure) ─────────────────
        if resp.status_code == 400:
            await self.db.update_task_failed(task_id)
            logger.error("400 permanent failure (task %d): %s", task_id, resp.text)
            return

        # ── Unexpected status ───────────────────────────────────
        logger.warning("Unexpected %d (task %d): %s", resp.status_code, task_id, resp.text)
        await self._schedule_retry(task_id, retry_count)

    # ── Retry helpers ───────────────────────────────────────────

    async def _schedule_retry(self, task_id: int, current_retry: int):
        next_retry = current_retry + 1
        if next_retry >= config.MAX_RETRIES:
            await self.db.update_task_failed(task_id)
            logger.error("DM failed after %d retries: task=%d", config.MAX_RETRIES, task_id)
        else:
            backoff = min(2 ** next_retry, 60)  # 2, 4, 8, 16, 32, 60 …
            next_at = time.time() + backoff
            await self.db.update_task_retry(task_id, next_retry, next_at)
            logger.info("Retry %d/%d in %ds: task=%d", next_retry, config.MAX_RETRIES, backoff, task_id)
