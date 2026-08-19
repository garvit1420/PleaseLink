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
        # Create Rule PRICE just in case
        await client.post(f"{URL}/rules", json={"keyword": "PRICE", "dm_message": "Hello!"})

        # --- Subtest A: Deleted before Created ---
        print("\n--- Subtest A: Deleted arrives before Created ---")
        cmt_id_A = f"cmt_A_{uuid.uuid4().hex[:6]}"
        user_id_A = f"usr_A_{uuid.uuid4().hex[:6]}"

        del_payload = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.deleted",
            "data": {"comment_id": cmt_id_A, "post_id": "post_1", "text": "PRICE plz", "from": {"user_id": user_id_A}}
        }
        raw_del = json.dumps(del_payload).encode()
        r = await client.post(f"{URL}/webhook", content=raw_del, headers={"X-PseudoGram-Signature": sign_payload(raw_del)})
        print("Webhook (comment.deleted) response:", r.status_code)
        
        await asyncio.sleep(2) # let background worker process it
        
        # Verify in deleted_comments
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT * FROM deleted_comments WHERE comment_id='{cmt_id_A}'"})
        print(f"deleted_comments for {cmt_id_A}:", r_query.json().get("rows"))

        # Send Created
        cre_payload = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.created",
            "data": {"comment_id": cmt_id_A, "post_id": "post_1", "text": "PRICE plz", "from": {"user_id": user_id_A}}
        }
        raw_cre = json.dumps(cre_payload).encode()
        r = await client.post(f"{URL}/webhook", content=raw_cre, headers={"X-PseudoGram-Signature": sign_payload(raw_cre)})
        print("Webhook (comment.created) response:", r.status_code)

        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT * FROM dm_tasks WHERE comment_id='{cmt_id_A}'"})
        tasks = r_query.json().get("rows", [])
        print(f"dm_tasks created for {cmt_id_A} (should be 0):", len(tasks))

        # --- Subtest B: Created then Deleted ---
        print("\n--- Subtest B: Created then Deleted ---")
        cmt_id_B = f"cmt_B_{uuid.uuid4().hex[:6]}"
        user_id_B = f"usr_B_{uuid.uuid4().hex[:6]}"
        
        cre_payload_B = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.created",
            "data": {"comment_id": cmt_id_B, "post_id": "post_1", "text": "PRICE plz", "from": {"user_id": user_id_B}}
        }
        raw_cre_B = json.dumps(cre_payload_B).encode()
        r = await client.post(f"{URL}/webhook", content=raw_cre_B, headers={"X-PseudoGram-Signature": sign_payload(raw_cre_B)})
        print("Webhook (comment.created) response:", r.status_code)

        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT id, status FROM dm_tasks WHERE comment_id='{cmt_id_B}'"})
        tasks = r_query.json().get("rows", [])
        print(f"dm_tasks created for {cmt_id_B} (should be 1):", tasks)

        del_payload_B = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.deleted",
            "data": {"comment_id": cmt_id_B, "post_id": "post_1", "text": "PRICE plz", "from": {"user_id": user_id_B}}
        }
        raw_del_B = json.dumps(del_payload_B).encode()
        r = await client.post(f"{URL}/webhook", content=raw_del_B, headers={"X-PseudoGram-Signature": sign_payload(raw_del_B)})
        print("Webhook (comment.deleted) response:", r.status_code)

        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT id, status FROM dm_tasks WHERE comment_id='{cmt_id_B}'"})
        tasks = r_query.json().get("rows", [])
        print(f"dm_tasks status for {cmt_id_B} (should be cancelled if not sent):", tasks)

asyncio.run(main())
