import asyncio
import httpx
import json

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("1. Wiping DB...")
        r = await client.delete(f"{URL}/debug/wipe")
        print("Wipe:", r.status_code, r.text)

        print("2. Creating Rule 'PRICE'...")
        r = await client.post(f"{URL}/rules", json={"keyword": "PRICE", "dm_message": "Hello!"})
        print("Rule:", r.status_code, r.text)

        print("3. Triggering Simulation (count=20)...")
        r = await client.post(
            f"{MOCK_API}/v1/simulate/start",
            json={"webhook_url": f"{URL}/webhook", "count": 20, "duration_seconds": 2},
            headers={"X-API-Key": API_KEY}
        )
        print("Sim Start:", r.status_code, r.text)
        
        print("\n4. Polling /debug/query for dm_tasks transitions...")
        task_history = {}
        for _ in range(40):
            await asyncio.sleep(1.5)
            r = await client.post(f"{URL}/debug/query", json={"query": "SELECT id, status, retry_count FROM dm_tasks"})
            if r.status_code != 200:
                print("Query error:", r.status_code, r.text)
                continue
            
            rows = r.json().get("rows", [])
            for row in rows:
                tid = row["id"]
                status = row["status"]
                retries = row["retry_count"]
                
                if tid not in task_history:
                    task_history[tid] = []
                
                # record status if it changed
                if not task_history[tid] or task_history[tid][-1] != (status, retries):
                    task_history[tid].append((status, retries))
        
        print("\n=== FINAL TRANSITIONS ===")
        for tid, history in task_history.items():
            path = " -> ".join([f"{s}(r:{r})" for s, r in history])
            print(f"Task {tid}: {path}")

asyncio.run(main())
