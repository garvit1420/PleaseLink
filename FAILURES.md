# FAILURES.md — Known Failure Modes & Limitations

This document lists the honest technical limitations, quirks, and potential failure modes discovered during our end-to-end testing against the live PseudoGram Mock API.

---

1. **SQLite-on-Ephemeral-Disk Data Loss on Render Free Tier**
   Because we deployed the application using Render's free tier without mounting a Persistent Disk, the `data/linkplease.db` SQLite database is stored on the container's ephemeral file system. Render automatically spins down free web services after 15 minutes of inactivity. When the server wakes back up, the ephemeral disk is completely wiped and reset, permanently destroying all automation rules, cached webhook payloads, and `/stats` totals. 
   - **Mitigation used:** An external keep-alive ping (e.g., UptimeRobot polling every 5 minutes) prevents the server from sleeping. However, this does not protect against data wipes caused by normal git redeploys or container crashes. 
   - **Full fix:** Migrate from local SQLite to a remote persistent database (like PostgreSQL or MongoDB) or mount a Persistent Disk.

2. **Webhook Durability (raw_events Table) Limitations**
   To prevent dropping webhooks during processing crashes, the `/webhook` endpoint synchronously saves all incoming raw payloads to the `raw_events` SQLite table before returning a `200 OK`. A background loop (`event_processor`) then safely polls and processes them. 
   - **Remaining failure mode:** If the Node/Uvicorn process receives a hard kill (e.g., OOM kill, hardware power loss) at the exact millisecond the sqlite WAL journal is syncing to disk, the uncommitted transaction may roll back on restart, losing the event. Additionally, if the Render ephemeral disk is wiped (see point 1) before the background worker can process the `raw_events` backlog, those webhooks are lost forever.

3. **HMAC Signature Secret Quirk (Debugging Note)**
   During testing, we discovered a quirk in the PseudoGram Mock API's signature generation: the API signs webhooks using **only the base64-decoded email portion** of the API key, not the full API key string. 
   - For example, if the API key is `Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9`, the mock API computes the HMAC-SHA256 signature using the secret `"gbgarvit78@gmail.com"` (the decoded first half). We correctly adapted `config.py` to extract this specific secret to successfully pass signature verification.

4. **Rate-Limit Drain Time and Stats Polling**
   The PseudoGram Mock API strictly enforces a rate limit of approximately 9 requests per 60 seconds. A large burst simulation (e.g., 500 webhooks) can generate hundreds of valid matching DM tasks instantly. Because the background `dm_sender` respects the rate limit and queues the DMs, a large batch can take 10+ minutes to fully drain.
   - **Impact:** If an observer manually checks `/stats` too early after a burst, they will see high `queued` counts and low `sent` counts. This is working as intended (protecting against 429 Too Many Requests), but can appear as if DMs are failing if not monitored until the queue reaches 0.

5. **Simulated Truth `expected_stats` Missing from Early API Responses**
   The Mock API's `GET /v1/simulate/{run_id}/truth` endpoint does not immediately supply `expected_stats` while the status is `"running"`. Furthermore, when it finally transitions to `"complete"`, it provides `"expected_unique_recipient_count"` rather than exact send/duplicate breakdowns. Additionally, the Mock API deletes the run data after roughly 10 minutes. 
   - **Impact:** Automated scripts polling for the final truth table (e.g., `wait_for_completion.py`) must be careful to fetch the truth shortly after the simulation ends, rather than waiting 15+ minutes for the local DM queue to drain, otherwise the Mock API will return `404 Not Found`.
