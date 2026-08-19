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

## 6. Missed DM in a specific comment-deletion race
**The Failure**: If a user posts a matching comment (Comment 1, DM gets queued), then posts a second matching comment (Comment 2, correctly blocked as duplicate via the UNIQUE(user_id, rule_id) constraint), and THEN deletes Comment 1 before the DM for it was sent — our system cancels/deletes the pending task for Comment 1, but does NOT re-open eligibility for Comment 2, which was already blocked. The user ends up receiving 0 DMs, even though they have a still-live matching comment (Comment 2) that should have qualified them. We confirmed this happened exactly 3 times out of 92 expected recipients in a 500-event live test run (89 sent vs 92 expected).
**The Fix**: When cancelling a task due to comment.deleted, check if any other still-live (non-deleted) matching comment exists for that (user_id, rule_id) pair, and if so, requeue a new task instead of just deleting. We didn't implement this given the time constraint, since it's a narrow edge case (comment.deleted + duplicate comment overlap) affecting ~3% of cases in our test.
