import asyncio
import httpx
import json
import time

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("1. Wiping DB...")
        await client.delete(f"{URL}/debug/wipe")
        
        print("2. Creating Rule 'PRICE'...")
        await client.post(f"{URL}/rules", json={"keyword": "PRICE", "dm_message": "Hello!"})
        
        print("3. Triggering 500-event Simulation...")
        r_sim = await client.post(
            f"{MOCK_API}/v1/simulate/start",
            json={"webhook_url": f"{URL}/webhook", "count": 500, "duration_seconds": 10},
            headers={"X-API-Key": API_KEY}
        )
        run_id = r_sim.json().get("run_id")
        print("Sim Start:", r_sim.status_code, "Run ID:", run_id)
        
        print("4. Waiting for webhooks to arrive (15s)...")
        await asyncio.sleep(15)

        print("\n5. Polling for queue to drain...")
        while True:
            r_stats = await client.get(f"{URL}/stats")
            stats = r_stats.json()
            queued = stats.get("queued", 0)
            print(f"Stats: {stats}")
            if queued == 0 and stats.get("sent", 0) > 0:
                break
            await asyncio.sleep(5)
            
        print("\n6. Verifying raw_events count...")
        r_query = await client.post(f"{URL}/debug/query", json={"query": "SELECT COUNT(*) as count FROM raw_events"})
        count = r_query.json().get("rows", [{}])[0].get("count")
        print("Total raw_events received:", count)

        print("7. Verifying counters (rate limit check)...")
        r_query = await client.post(f"{URL}/debug/query", json={"query": "SELECT * FROM counters"})
        counters = r_query.json().get("rows", [])
        for c in counters:
            print(f"Counter {c['id']}: {c['value']}")
        
        print("\n=== FINAL TEST 3 REPORT ===")
        print(f"Total raw_events: {count} (Expected: 500)")
        print(f"Final Stats: {stats}")
        print("Check if duplicates_blocked matches expected unique recipients logic.")
        
asyncio.run(main())
