import asyncio
import httpx
import os
import sys

API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
MOCK_API_BASE = "https://pseudogram-api.onrender.com"

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r_sim = await client.post(
            f"{MOCK_API_BASE}/v1/simulate/start",
            json={
                "webhook_url": "https://pleaselink.onrender.com/webhook",
                "count": 50,
                "duration_seconds": 2
            },
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"}
        )
        run_id = r_sim.json().get("run_id")
        print("Run ID:", run_id)
        
        for _ in range(60):
            await asyncio.sleep(5)
            r_truth = await client.get(
                f"{MOCK_API_BASE}/v1/simulate/{run_id}/truth",
                headers={"X-API-Key": API_KEY}
            )
            print("Truth:", r_truth.status_code, r_truth.json())
            if r_truth.json().get("status") == "completed":
                print("TRUTH ATTAINED!")
                break

asyncio.run(main())
