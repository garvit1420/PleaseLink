"""
Delivery reconciler (Part C) — catches the ~15 % of DMs that the API
accepts (202) but later reports as failed.

Polls  GET /v1/dm/{dm_id}  which does NOT count against the rate limit,
so we can call it as aggressively as we want.

If a DM has failed, we re-queue it for the sender to retry.
"""

import asyncio
import time
import logging

import httpx

from app.database import Database
from app import config

logger = logging.getLogger(__name__)


class Reconciler:
    def __init__(self, db: Database):
        self.db = db
        self.client = httpx.AsyncClient(
            base_url=config.BASE_URL,
            headers={"X-API-Key": config.API_KEY},
            timeout=30.0,
        )
        self._running = True

    # ── Lifecycle ───────────────────────────────────────────────

    async def run(self):
        logger.info("Reconciler started (interval=%ds)", config.RECONCILE_INTERVAL)
        while self._running:
            try:
                await self._reconcile_batch()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Reconciler error")

            await asyncio.sleep(config.RECONCILE_INTERVAL)

    def stop(self):
        self._running = False

    async def close(self):
        await self.client.aclose()

    # ── Core logic ──────────────────────────────────────────────

    async def _reconcile_batch(self):
        tasks = await self.db.get_accepted_tasks()
        if not tasks:
            return

        logger.debug("Reconciling %d accepted DMs", len(tasks))

        for task in tasks:
            await self._check_one(task)

    async def _check_one(self, task: dict):
        task_id = task["id"]
        dm_id = task["dm_id"]

        try:
            resp = await self.client.get(f"/v1/dm/{dm_id}")
        except httpx.RequestError as exc:
            logger.warning("Network error checking dm %s: %s", dm_id, exc)
            return  # will retry next cycle

        if resp.status_code != 200:
            logger.warning("Unexpected %d checking dm %s", resp.status_code, dm_id)
            return

        data = resp.json()
        status = data.get("status")

        if status == "delivered":
            await self.db.update_task_delivered(task_id)
            logger.info("✓ DM delivered: task=%d dm=%s", task_id, dm_id)

        elif status == "failed":
            retry_count = task["retry_count"] + 1
            if retry_count >= config.MAX_RETRIES:
                await self.db.update_task_failed(task_id)
                logger.error("DM delivery failed permanently: task=%d dm=%s", task_id, dm_id)
            else:
                backoff = min(2 ** retry_count, 60)
                next_at = time.time() + backoff
                await self.db.update_task_retry(task_id, retry_count, next_at)
                logger.warning(
                    "DM delivery failed, re-queuing: task=%d dm=%s retry=%d/%d",
                    task_id, dm_id, retry_count, config.MAX_RETRIES,
                )

        # status == "queued" → still in transit, check again next cycle
