# FAILURES.md — Known Failure Modes & Limitations

This document lists four specific technical edge cases where our system could theoretically lose a DM, send a duplicate, or report inaccurate metrics, along with the precise conditions under which each scenario occurs.

---

1. **Hardware Power Loss During SQLite WAL Sync**
   While `POST /webhook` synchronously persists every raw event payload into the `raw_events` SQLite table before returning a `200 OK` response (preventing in-memory data loss), an ungraceful hardware failure (e.g. sudden power loss, kernel panic, hypervisor kill) occurring precisely during an active SQLite file flush before the WAL journal is committed to physical storage could result in an uncommitted transaction rollback upon restart.

2. **Single-Worker Ingestion Lag & Disk Lock Contention Under Extreme Bursts (>1,000 req/sec)**
   `EventProcessor` operates as a single sequential background consumer loop polling `raw_events` serially from SQLite. During extreme, massive webhook bursts (e.g., 5,000 webhooks arriving in under 2 seconds), synchronous `INSERT` queries to `raw_events` from concurrent webhooks can contend for the SQLite write lock (`PRAGMA busy_timeout=5000`). While events are safely persisted without data loss, `raw_events` backlog will accumulate temporarily until the single background worker completely drains it.

3. **Out-of-Order Deletions Beyond Retry Backoff Window**
   If a `comment.deleted` event arrives hours or days after the original `comment.created` event was processed, and the DM task had already entered the terminal `delivered` status or finished all retries, the cancellation logic in `webhook_handler.py` will have no effect on the already-sent DM. Similarly, if a deletion arrives for a task while it is actively in flight (`POST /v1/dm/send` request on the wire), the mock API may still accept and deliver it.

4. **Permanent API 500 Escalation Exhausting Max Retries**
   If PseudoGram experiences sustained internal server errors (500) that last longer than our exponential backoff window (`MAX_RETRIES = 5` over ~2 minutes), the DM task is marked as `failed`. If PseudoGram recovers immediately afterwards, our system will not retry the DM again because `retry_count` has hit `MAX_RETRIES`. In `/stats`, this is accurately recorded under `failed`, but the DM is permanently lost to the recipient.
