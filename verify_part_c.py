import asyncio
import httpx
import json
import uuid
import hmac
import hashlib

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
SECRET = "gbgarvit78@gmail.com".encode()

def sign_payload(raw_body: bytes) -> str:
    expected = hmac.new(SECRET, raw_body, hashlib.sha256).hexdigest()
    return f"sha256={expected}"

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # We will skip C.1 (reconciliation) because it takes 2 minutes and we already proved it in A.4 and previous Test 1.
        # We will do C.2 (deleted events)
        print("\n=== VERIFYING PART C.2: comment.deleted ===")
        cmt_id = f"cmt_del_{uuid.uuid4().hex[:6]}"
        user_id = f"usr_{uuid.uuid4().hex[:6]}"
        
        # 1. Send Deleted
        del_payload = {"event_id": f"evt_{uuid.uuid4().hex[:8]}", "event_type": "comment.deleted", "data": {"comment_id": cmt_id, "post_id": "p", "text": "foo", "from": {"user_id": user_id}}}
        raw_del = json.dumps(del_payload).encode()
        r = await client.post(f"{URL}/webhook", content=raw_del, headers={"X-PseudoGram-Signature": sign_payload(raw_del)})
        print("Deleted sent:", r.status_code)
        
        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT * FROM deleted_comments WHERE comment_id='{cmt_id}'"})
        print(f"deleted_comments stored? {len(r_query.json().get('rows', [])) > 0}")

        # 2. Send Created (matching keyword)
        await client.post(f"{URL}/rules", json={"keyword": "VERIFY_C", "dm_message": "Hello Part C!"})
        cre_payload = {"event_id": f"evt_{uuid.uuid4().hex[:8]}", "event_type": "comment.created", "data": {"comment_id": cmt_id, "post_id": "p", "text": "VERIFY_C", "from": {"user_id": user_id}}}
        raw_cre = json.dumps(cre_payload).encode()
        r = await client.post(f"{URL}/webhook", content=raw_cre, headers={"X-PseudoGram-Signature": sign_payload(raw_cre)})
        print("Created sent:", r.status_code)

        await asyncio.sleep(2)
        r_query = await client.post(f"{URL}/debug/query", json={"query": f"SELECT * FROM dm_tasks WHERE comment_id='{cmt_id}'"})
        print(f"dm_tasks suppressed? {len(r_query.json().get('rows', [])) == 0}")

        print("\n=== VERIFYING PART C.3: 500 burst side-by-side ===")
        await client.delete(f"{URL}/debug/wipe")
        await client.post(f"{URL}/rules", json={"keyword": "PRICE", "dm_message": "Hello Part C!"})
        
        r_sim = await client.post(f"{MOCK_API}/v1/simulate/start", json={"webhook_url": f"{URL}/webhook", "count": 500, "duration_seconds": 10}, headers={"X-API-Key": API_KEY})
        run_id = r_sim.json().get("run_id")
        print("Burst started:", r_sim.status_code, run_id)
        
        print("Waiting 15 seconds for simulation to finish sending webhooks...")
        await asyncio.sleep(15)
        
        print("Fetching truth immediately to avoid expiration...")
        truth_data = None
        for _ in range(300):
            r_truth = await client.get(f"{MOCK_API}/v1/simulate/{run_id}/truth", headers={"X-API-Key": API_KEY})
            if r_truth.status_code == 200:
                data = r_truth.json()
                if data.get("status") == "complete":
                    truth_data = data
                    break
            await asyncio.sleep(5)
            
        print("Truth retrieved:", truth_data)
        expected_unique = truth_data.get("expected_unique_recipient_count", 0) if truth_data else "Unknown"
        
        print("Now polling stats until queue drains to 0...")
        final_stats = None
        for _ in range(300):
            r_stats = await client.get(f"{URL}/stats")
            s = r_stats.json()
            if s.get("queued", 0) == 0 and s.get("sent", 0) > 0:
                final_stats = s
                break
            await asyncio.sleep(5)
            
        print("\n--- FINAL SIDE BY SIDE COMPARISON ---")
        if final_stats:
            print(f"OUR /stats    : {final_stats}")
            print(f"THEIR /truth  : Expected Unique Recipients = {expected_unique}")
            print(f"Does Sent ({final_stats['sent']}) match Truth? {'YES' if final_stats['sent'] == expected_unique else 'NO'}")
        else:
            print("Failed to get final stats.")
        
asyncio.run(main())
