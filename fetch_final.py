import asyncio
import httpx

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
RUN_ID = "run_2f15d415ecdc"

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        r_truth = await client.get(f"{MOCK_API}/v1/simulate/{RUN_ID}/truth", headers={"X-API-Key": API_KEY})
        truth = r_truth.json()
        print("Truth:", truth)
        expected = truth.get("expected_unique_recipient_count", "Unknown")
        
        while True:
            r_stats = await client.get(f"{URL}/stats")
            s = r_stats.json()
            print("Stats:", s)
            if s.get("queued", 0) == 0 and s.get("sent", 0) > 0:
                print("\n--- FINAL ---")
                print(f"Sent: {s['sent']} | Expected: {expected}")
                if s['sent'] == expected:
                    print("SUCCESS! PERFECT MATCH!")
                break
            await asyncio.sleep(5)

asyncio.run(main())
