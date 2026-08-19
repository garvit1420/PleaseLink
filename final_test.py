import asyncio
import httpx
import time

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"

async def main():
    print("--- STARTING FINAL ISOLATED TEST ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Checking baseline stats to confirm DB is wiped...")
        r_stats = await client.get(f"{URL}/stats")
        print("Baseline Stats:", r_stats.json())
        
        print("\nCreating rule...")
        r_rule = await client.post(f"{URL}/rules", json={"keyword": "PRICE", "dm_message": "Hello Final Test!"})
        print("Rule created:", r_rule.status_code)
        
        print("\nTriggering simulation...")
        r_sim = await client.post(f"{MOCK_API}/v1/simulate/start", json={"webhook_url": f"{URL}/webhook", "count": 500, "duration_seconds": 10}, headers={"X-API-Key": API_KEY})
        run_id = r_sim.json().get("run_id")
        print("Burst started:", r_sim.status_code, run_id)
        
        print("\nPolling stats until queue drains...")
        truth_data = None
        while True:
            r_stats = await client.get(f"{URL}/stats")
            s = r_stats.json()
            print(f"Live stats: {s}")
            
            if not truth_data:
                r_truth = await client.get(f"{MOCK_API}/v1/simulate/{run_id}/truth", headers={"X-API-Key": API_KEY})
                t = r_truth.json()
                if t.get("status") == "complete":
                    truth_data = t
                    print(f"Mock API Truth Expected Unique Recipients: {truth_data.get('expected_unique_recipient_count')}")
            
            if truth_data and s.get("queued", 0) == 0 and s.get("sent", 0) > 0:
                print("\n--- FINAL SIDE BY SIDE COMPARISON ---")
                print(f"Expected (Truth): {truth_data.get('expected_unique_recipient_count')}")
                print(f"Sent (Delivered): {s.get('sent')}")
                print(f"Failed:           {s.get('failed')}")
                print(f"Duplicates Blocked: {s.get('duplicates_blocked')}")
                break
            
            await asyncio.sleep(5)

asyncio.run(main())
