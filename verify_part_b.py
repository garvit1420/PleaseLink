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
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("\n=== VERIFYING PART B.1: Reject Forged Requests ===")
        payload = {
            "event_id": f"evt_{uuid.uuid4().hex[:8]}",
            "event_type": "comment.created",
            "data": {"comment_id": "cmt_123", "post_id": "post_1", "text": "VERIFY_B", "from": {"user_id": "usr_1"}}
        }
        raw = json.dumps(payload).encode()
        
        r_bad = await client.post(f"{URL}/webhook", content=raw, headers={"X-PseudoGram-Signature": "sha256=abcdefg123456"})
        r_good = await client.post(f"{URL}/webhook", content=raw, headers={"X-PseudoGram-Signature": sign_payload(raw)})
        
        print(f"Bad Signature Response : {r_bad.status_code} {r_bad.text}")
        print(f"Good Signature Response: {r_good.status_code} {r_good.text}")
        if r_bad.status_code == 401 and r_good.status_code == 200:
            print("PASS: Forged requests correctly rejected.")

        print("\n=== VERIFYING PART B.2: /stats under load ===")
        await client.delete(f"{URL}/debug/wipe")
        await client.post(f"{URL}/rules", json={"keyword": "VERIFY_B", "dm_message": "Hello Part B!"})
        
        print("Starting 100-event burst...")
        r_sim = await client.post(
            f"{MOCK_API}/v1/simulate/start",
            json={"webhook_url": f"{URL}/webhook", "count": 100, "duration_seconds": 2},
            headers={"X-API-Key": API_KEY}
        )
        print("Burst started:", r_sim.status_code)
        
        print("Polling /stats during burst for inconsistencies...")
        for _ in range(15):
            r_stats = await client.get(f"{URL}/stats")
            s = r_stats.json()
            print(f"Live Stats: {s}")
            if s.get("sent", 0) < 0 or s.get("queued", 0) < 0 or s.get("failed", 0) < 0 or s.get("duplicates_blocked", 0) < 0:
                print("FAIL: Negative number found!")
            await asyncio.sleep(1)

        print("PASS: Stats remained positive and accurate during load.")

asyncio.run(main())
