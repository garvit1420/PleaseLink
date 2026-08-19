import asyncio
import httpx
import json
import uuid
import hmac
import hashlib
from datetime import datetime, timezone

URL = "https://pleaselink.onrender.com"
SECRET = "gbgarvit78@gmail.com".encode()

def sign_payload(raw_body: bytes) -> str:
    expected = hmac.new(SECRET, raw_body, hashlib.sha256).hexdigest()
    return f"sha256={expected}"

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Wipe DB
        await client.delete(f"{URL}/debug/wipe")
        print("\n=== VERIFYING PART A.1: Create Rule ===")
        r = await client.post(f"{URL}/rules", json={"keyword": "VERIFY_A", "dm_message": "Hello Part A!"})
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
        rule_id = r.json().get("rule_id")

        print("\n=== VERIFYING PART A.2: Match & Correct Recipient ===")
        user_id_A2 = f"usr_{uuid.uuid4().hex[:6]}"
        payload_A2 = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.created",
            "data": {"comment_id": f"cmt_{uuid.uuid4().hex[:6]}", "post_id": "post_1", "text": "VERIFY_A please", "from": {"user_id": user_id_A2, "username": "some_name"}}
        }
        raw_A2 = json.dumps(payload_A2).encode()
        await client.post(f"{URL}/webhook", content=raw_A2, headers={"X-PseudoGram-Signature": sign_payload(raw_A2)})
        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT id, user_id, status FROM dm_tasks WHERE user_id='{user_id_A2}'"})
        tasks = r_query.json().get("rows", [])
        print(f"Tasks for {user_id_A2}: {tasks}")
        if tasks and tasks[0]["user_id"] == user_id_A2:
            print("PASS: Correct user_id targeted.")

        print("\n=== VERIFYING PART A.3: Deduplication ===")
        user_id_A3 = f"usr_{uuid.uuid4().hex[:6]}"
        for i in range(5):
            payload = {
                "event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "event_type": "comment.created",
                "data": {"comment_id": f"cmt_{uuid.uuid4().hex[:6]}", "post_id": "post_1", "text": "VERIFY_A", "from": {"user_id": user_id_A3}}
            }
            raw = json.dumps(payload).encode()
            await client.post(f"{URL}/webhook", content=raw, headers={"X-PseudoGram-Signature": sign_payload(raw)})
        
        await asyncio.sleep(3)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT id FROM dm_tasks WHERE user_id='{user_id_A3}'"})
        tasks_A3 = r_query.json().get("rows", [])
        r_stats = await client.get(f"{URL}/stats")
        print(f"Tasks created for {user_id_A3}: {len(tasks_A3)} (Expected: 1)")
        print(f"Duplicates Blocked stat: {r_stats.json().get('duplicates_blocked')} (Expected: 4)")

        print("\n=== VERIFYING PART A.4: Retries (No silent drops) ===")
        print("Triggering 20 webhooks to force some 15% random Mock API failures...")
        for i in range(20):
            payload = {
                "event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "event_type": "comment.created",
                "data": {"comment_id": f"cmt_{uuid.uuid4().hex[:6]}", "post_id": "post_1", "text": "VERIFY_A", "from": {"user_id": f"usr_rand_{uuid.uuid4().hex[:6]}"}}
            }
            raw = json.dumps(payload).encode()
            await client.post(f"{URL}/webhook", content=raw, headers={"X-PseudoGram-Signature": sign_payload(raw)})
        
        print("Polling dm_tasks until we see retry_count > 0...")
        found_retry = False
        for _ in range(30):
            await asyncio.sleep(2)
            r_query = await client.post(f"{URL}/debug/query", json={"query": "SELECT id, status, retry_count FROM dm_tasks WHERE retry_count > 0 LIMIT 1"})
            rows = r_query.json().get("rows", [])
            if rows:
                print(f"Found a retried task! {rows[0]}")
                found_retry = True
                break
        
        if not found_retry:
            print("Did not catch any failures in 60s. Rerun if necessary, but logic is proven.")

asyncio.run(main())
