# Honest Testing & Failure Log

This document records the actual failures, quirks, and debugging discoveries made during the systematic verification of the LinkPlease webhook processor.

## 1. SQLite-on-ephemeral-disk Data Loss
**The Failure**: During long-running tests with time gaps (e.g., waiting 50 minutes for stats to drain), the Render free tier container would spin down due to inactivity. Because Render free tier uses ephemeral disks, spinning down wipes the SQLite database entirely, resulting in all stats dropping to 0 and all queued DMs being lost.
**The Fix/Mitigation**: We mitigated this during testing by keeping the container awake with an external ping. However, this does not protect against crashes or redeploys wiping the disk. 
**Long-term Fix**: A proper production deployment must migrate to a persistent database like PostgreSQL.

## 2. Webhook Durability (Crash Recovery)
**The Failure**: If the application crashes during event processing, webhooks that were received but not yet processed would be permanently lost.
**The Fix**: We implemented a `raw_events` table that synchronously stores incoming webhooks to the SQLite database *before* returning a `200 OK`. Background workers then poll this table asynchronously.
**Lingering Risks**: Because SQLite is on an ephemeral disk, if the server crashes *and is restarted on a new container*, the `raw_events` table is wiped along with the rest of the database, meaning the durability fix is completely undermined by the hosting environment. 

## 3. The Mock API HMAC Signature Quirk
**The Failure**: In Part B, signature validation failed initially. We assumed the API key (`Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9`) was being used directly as the secret key for the HMAC-SHA256 signature.
**The Fix**: Through deep debugging, we discovered a deliberate quirk in the Mock API: the pseudo-signature actually uses the base64-decoded email portion of the API key as the secret, NOT the full API key string. This required extracting the secret logic in `config.py`.

## 4. Rate-Limit Drain Time
**The Failure**: During burst tests (e.g., 500 events), querying `/stats` immediately after the Mock API finished sending webhooks would show a high `queued` count but a very low `sent` count. We initially mistook this for a failure in processing speed.
**The Fix**: This was actually the Mock API's strict rate limit working exactly as designed! The Mock API restricts DMs to 9 requests per 60 seconds (with a small burst capacity). A batch of 150 DMs legitimately takes over 15 minutes to fully drain. We had to implement a 15-20 minute polling loop in our test scripts to wait for `queued` to reach 0.

## 5. The "Cancelled Deduplication" Bug (Missing DMs)
**The Failure**: During our final 500-event side-by-side Truth verification, our `sent` count was exactly 7 lower than the Mock API's `expected_unique_recipient_count`. 
**The Investigation**: We discovered that 7 users had deleted their original comments *before* we processed their DMs. Our code correctly cancelled those pending DMs. However, when those same users posted a *second* comment containing the keyword, our `create_dm_task` function threw an `IntegrityError` because of a `UNIQUE(user_id, rule_id)` constraint in the database, blocking them as duplicates.
**The Fix**: Because the user never actually received the first DM (it was cancelled), they were still eligible to receive a DM. We fixed this by modifying `cancel_pending_dms_for_comment` to `DELETE` the cancelled task from the database instead of just updating its status to 'cancelled', thereby freeing up the UNIQUE constraint and allowing the user to be processed on their subsequent comment.

## 6. Unverifiable Missing DMs (comment.deleted race condition)
**The Failure**: 2 out of 99 expected recipients did not receive a DM in a 500-event load test (96 sent + 1 failed = 97 of 99 expected). The mock API's `/truth` endpoint only returns an aggregate `expected_unique_recipients` list, not per-event payloads, so I could not directly confirm the cause against raw event data for this specific run.
**The Fix/Theory**: Based on local testing where I did have DB access, the most likely explanation is: a user's first comment queues a DM, a duplicate second comment is correctly blocked, then the first comment gets deleted and cancels the pending DM — leaving them with 0 DMs despite being counted as an expected recipient. This is a theory consistent with the numbers, not a confirmed root cause for this specific run.

## 7. Lack of Persistent Historical Debug Data
**The Failure**: Raw events are stored in SQLite on Render's free tier, which uses an ephemeral disk. Any redeploy wipes the database, so historical events from a completed run can't be inspected after the fact for debugging. 
**The Fix**: Moving to Postgres (or any persistent volume) would fix this and let me verify edge cases like the one above against real data instead of inference.

## 8. Misleading Early Stats Reads (Rate Limit Drain)
**The Failure**: Full 500-event queue drain takes ~16 minutes due to the mock API's strict 9 DMs/min rate limit. 
**The Fix**: If `/stats` is checked immediately after a burst, sent/queued numbers reflect an in-progress state, not final totals. We must actively wait for `queued` to reach 0 before attempting to reconcile data against truth.
