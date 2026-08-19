import asyncio
import httpx
import time
import uuid, hmac, hashlib
from app.config import API_KEY

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Resetting DB via API / script SQL...")
        # Clean data tables via sqlite3 connection or requests
        import sqlite3
        conn = sqlite3.connect('data/linkplease.db')
        conn.execute("DELETE FROM rules;")
        conn.execute("DELETE FROM raw_events;")
        conn.execute("DELETE FROM processed_events;")
        conn.execute("DELETE FROM dm_tasks;")
        conn.execute("DELETE FROM deleted_comments;")
        conn.execute("UPDATE counters SET value = 0;")
        conn.commit()
        conn.close()
        print("   Database reset to clean 0 state.")

        print("2. Creating rule 'TEST'...")
        await client.post("http://localhost:8000/rules", json={
            "keyword": "TEST",
            "dm_message": "Stress test rule DM"
        })
        
        async def sign_and_send(payload):
            raw_body = httpx.Request('POST', 'http://localhost:8000/webhook', json=payload).read()
            sig = "sha256=" + hmac.new(API_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
            t0 = time.monotonic()
            resp = await client.post("http://localhost:8000/webhook", content=raw_body, headers={
                "X-PseudoGram-Signature": sig,
                "Content-Type": "application/json"
            })
            t1 = time.monotonic()
            return resp.status_code, (t1 - t0) * 1000.0

        print("3. Firing 500 requests...")
        tasks = []
        user_1 = "user_stress_1"
        comment_1 = "comm_stress_1"
        for i in range(50):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": comment_1 + str(i), "text": "I want a TEST", "from": {"user_id": user_1}}
            }))
            
        fixed_event_id = str(uuid.uuid4())
        for i in range(50):
            tasks.append(sign_and_send({
                "event_id": fixed_event_id,
                "event_type": "comment.created",
                "data": {"comment_id": "comm_fixed", "text": "give TEST", "from": {"user_id": "user_fixed"}}
            }))
            
        for i in range(400):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": f"comm_norm_{i}", "text": "TEST please", "from": {"user_id": f"user_norm_{i}"}}
            }))
            
        start_time = time.monotonic()
        results = await asyncio.gather(*tasks)
        end_time = time.monotonic()
        
        print(f"\nBurst complete in {end_time - start_time:.2f}s")
        
        # Checkpoint 0: Immediately
        r0 = await client.get("http://localhost:8000/stats")
        print("Checkpoint 0s  (Immediate) :", r0.json())
        
        # Checkpoint 10s: +10s
        print("Waiting 10 seconds...")
        await asyncio.sleep(10)
        r10 = await client.get("http://localhost:8000/stats")
        print("Checkpoint 10s (+10s)       :", r10.json())
        
        # Checkpoint 30s: +20s more (total 30s)
        print("Waiting 20 seconds more (+30s total)...")
        await asyncio.sleep(20)
        r30 = await client.get("http://localhost:8000/stats")
        print("Checkpoint 30s (+30s)       :", r30.json())

if __name__ == "__main__":
    asyncio.run(main())
