import asyncio
import httpx
import uuid
import hmac
import hashlib
import time
import numpy as np
from app.config import API_KEY, DB_PATH
from app.database import Database

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Creating rule 'TEST'...")
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
            latency_ms = (t1 - t0) * 1000.0
            return resp.status_code, latency_ms

        print("2. Firing 500 requests across burst payload batch...")
        tasks = []
        
        # 50 events from same user (tests user-rule dedup + DB concurrency)
        user_1 = "user_stress_1"
        comment_1 = "comm_stress_1"
        for i in range(50):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": comment_1 + str(i), "text": "I want a TEST", "from": {"user_id": user_1}}
            }))
            
        # 50 identical event_ids (tests event_id dedup with INSERT OR IGNORE)
        fixed_event_id = str(uuid.uuid4())
        for i in range(50):
            tasks.append(sign_and_send({
                "event_id": fixed_event_id,
                "event_type": "comment.created",
                "data": {"comment_id": "comm_fixed", "text": "give TEST", "from": {"user_id": "user_fixed"}}
            }))
            
        # 400 normal events from 400 different users
        for i in range(400):
            tasks.append(sign_and_send({
                "event_id": str(uuid.uuid4()),
                "event_type": "comment.created",
                "data": {"comment_id": f"comm_norm_{i}", "text": "TEST please", "from": {"user_id": f"user_norm_{i}"}}
            }))
            
        start_time = time.monotonic()
        results = await asyncio.gather(*tasks)
        end_time = time.monotonic()
        
        statuses = [r[0] for r in results]
        latencies = [r[1] for r in results]
        
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
        avg = float(np.mean(latencies))
        
        print(f"\n--- BENCHMARK RESULTS ---")
        print(f"Total webhooks sent: {len(results)}")
        print(f"Total time taken:    {end_time - start_time:.2f}s")
        print(f"Statuses received:   {set(statuses)}")
        print(f"Average Latency:     {avg:.2f} ms")
        print(f"p95 Latency:         {p95:.2f} ms")
        print(f"p99 Latency:         {p99:.2f} ms")
        print("-------------------------\n")
        
        print("3. Checking backlog & drain time in SQLite...")
        db = Database(DB_PATH)
        await db.connect()
        
        t_drain_start = time.monotonic()
        max_backlog = await db.count_unprocessed_raw_events()
        print(f"Initial unprocessed raw_events backlog immediately after burst: {max_backlog}")
        
        while True:
            unprocessed = await db.count_unprocessed_raw_events()
            if unprocessed > max_backlog:
                max_backlog = unprocessed
            if unprocessed == 0:
                break
            await asyncio.sleep(0.1)
            
        t_drain_end = time.monotonic()
        drain_time = t_drain_end - t_drain_start
        print(f"Max raw_events backlog observed: {max_backlog}")
        print(f"Time taken to drain backlog to 0: {drain_time:.2f} seconds\n")
        
        r = await client.get("http://localhost:8000/stats")
        print("FINAL /stats SNAPSHOT:", r.json())
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
