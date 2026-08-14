import asyncio
import httpx
import uuid
import hmac
import hashlib
from app.config import API_KEY

async def main():
    async with httpx.AsyncClient() as client:
        print("1. Creating rule 'TEST'...")
        await client.post("http://localhost:8000/rules", json={
            "keyword": "TEST",
            "dm_message": "Stress test rule DM"
        })
        
        def sign_and_send(payload):
            raw_body = httpx.Request('POST', 'http://localhost:8000/webhook', json=payload).read()
            sig = "sha256=" + hmac.new(API_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
            return client.post("http://localhost:8000/webhook", content=raw_body, headers={
                "X-PseudoGram-Signature": sig,
                "Content-Type": "application/json"
            })
            
        print("2. Firing 100 concurrent requests...")
        tasks = []
        
        # 10 identical events from same user (tests user-rule dedup + DB concurrency)
        user_1 = "user_stress_1"
        comment_1 = "comm_stress_1"
        for i in range(10):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": comment_1 + str(i), "text": "I want a TEST", "from": {"user_id": user_1}}
            }))
            
        # 10 identical event_ids (tests event_id dedup)
        fixed_event_id = str(uuid.uuid4())
        for i in range(10):
            tasks.append(sign_and_send({
                "event_id": fixed_event_id,
                "event_type": "comment.created",
                "data": {"comment_id": "comm_fixed", "text": "give TEST", "from": {"user_id": "user_fixed"}}
            }))
            
        # 80 normal events from 80 different users
        for i in range(80):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": f"comm_norm_{i}", "text": "TEST please", "from": {"user_id": f"user_norm_{i}"}}
            }))
            
        start_time = asyncio.get_event_loop().time()
        responses = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        print(f"3. Sent 100 requests in {end_time - start_time:.2f} seconds.")
        print(f"   Statuses: {set(r.status_code for r in responses)}")
        
        print("4. Checking stats immediately (webhook should have processed instantly)...")
        r = await client.get("http://localhost:8000/stats")
        print("STATS:", r.json())
        
        print("Done. Check server logs to see the rate limiter and sender working over the next few minutes.")

if __name__ == "__main__":
    asyncio.run(main())
