import os
import asyncio
import httpx
import json
import time
import sqlite3
import subprocess

# Enable signature verification
os.environ["SIGNATURE_VERIFICATION_ENABLED"] = "true"
os.environ["VERIFY_SIGNATURES"] = "true"

from app.config import API_KEY

MOCK_API_BASE = "https://pseudogram-api.onrender.com"

async def main():
    public_url = os.environ.get("PUBLIC_URL")
    print("1. Cleaning DB tables for clean 1-to-1 official simulation...")
    if public_url:
        async with httpx.AsyncClient(timeout=90.0) as client:
            print("   Waiting for Render to finish deploying (polling /debug/wipe)...")
            for _ in range(60):
                try:
                    r = await client.delete(f"{public_url}/debug/wipe")
                    if r.status_code == 200:
                        print("   Remote DB wiped on Render.")
                        break
                except Exception:
                    pass
                await asyncio.sleep(5)
            else:
                print("ERROR: Deploy taking too long or /debug/wipe not found.")
                return
    else:
        if os.path.exists("data/linkplease.db"):
            conn = sqlite3.connect("data/linkplease.db")
            conn.execute("DELETE FROM rules;")
            conn.execute("DELETE FROM raw_events;")
            conn.execute("DELETE FROM processed_events;")
            conn.execute("DELETE FROM dm_tasks;")
            conn.execute("DELETE FROM deleted_comments;")
            conn.execute("UPDATE counters SET value = 0;")
            conn.commit()
            conn.close()

    public_url = os.environ.get("PUBLIC_URL")
    lt_proc = None
    
    if not public_url:
        print("2. Starting localtunnel on port 8000...")
        lt_proc = subprocess.Popen(
            "npx localtunnel --port 8000",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        
        for _ in range(30):
            await asyncio.sleep(0.5)
            # Check if output contains URL
            if lt_proc.stdout:
                line = lt_proc.stdout.readline()
                if "your url is:" in line:
                    public_url = line.split("your url is:")[1].strip()
                    break

        if not public_url:
            print("ERROR: Failed to obtain localtunnel URL!")
            lt_proc.kill()
            return
        print(f"   Tunnel established: {public_url}/webhook")
    else:
        print(f"2. Using external PUBLIC_URL: {public_url}")

    public_webhook_url = f"{public_url}/webhook"

    async with httpx.AsyncClient(timeout=120.0) as client:
        print("3. Creating rule 'PRICE' on target server...")
        r_rule = await client.post(f"{public_url}/rules", json={
            "keyword": "PRICE",
            "dm_message": "Here's the price list: http://example.com/prices"
        })
        print("   Rule created:", r_rule.json())

        print(f"4. Triggering REAL Official Simulation at {MOCK_API_BASE}/v1/simulate/start...")
        sim_payload = {
            "webhook_url": public_webhook_url,
            "count": int(os.environ.get("SIM_COUNT", "500")),
            "duration_seconds": 10
        }
        r_sim = await client.post(
            f"{MOCK_API_BASE}/v1/simulate/start",
            json=sim_payload,
            headers={"X-API-Key": API_KEY, "Content-Type": "application/json"}
        )
        print("   Start Simulation Response Status:", r_sim.status_code)
        sim_data = r_sim.json()
        print("   Start Simulation Response Body:", sim_data)

        run_id = sim_data.get("run_id")
        if not run_id:
            print("ERROR: No run_id returned from PseudoGram simulation start!")
            if lt_proc:
                lt_proc.kill()
            return

        print(f"\n5. Simulation {run_id} running! Waiting 15 seconds for PseudoGram to send 500 webhooks...")
        await asyncio.sleep(15)

        print("6. Fetching Official Server-Side Ground Truth from PseudoGram...")
        r_truth = await client.get(
            f"{MOCK_API_BASE}/v1/simulate/{run_id}/truth",
            headers={"X-API-Key": API_KEY}
        )
        print("   Truth Status:", r_truth.status_code)
        truth_data = r_truth.json()

        print("7. Fetching /stats immediately after webhook burst...")
        r_stats_imm = await client.get(f"{public_url}/stats")
        our_stats_imm = r_stats_imm.json()

        print("\n========================================================")
        print("         OFFICIAL REAL-TIME GROUND TRUTH REPORT         ")
        print("========================================================")
        print(f"Run ID: {run_id}")
        print(f"Public Webhook URL: {public_webhook_url}\n")
        
        print(f"FULL OFFICIAL GROUND TRUTH RESPONSE:")
        print(json.dumps(truth_data, indent=2))
        print("\n--------------------------------------------------------")
        print(f"OUR LOCAL /stats SNAPSHOT (Immediately after 500 webhooks):")
        print(json.dumps(our_stats_imm, indent=2))
        print("--------------------------------------------------------\n")

        # Parse expected stats from truth response
        expected = truth_data.get("expected_stats", {})
        print("SIDE-BY-SIDE COMPUTED DIFFERENCES:")
        print(f"{'Field':<20} | {'Official Expected':<18} | {'Our /stats (Total)':<20} | {'Difference':<10}")
        print("-" * 75)

        exp_sent = expected.get("sent", 0)
        exp_failed = expected.get("failed", 0)
        exp_dups = expected.get("duplicates_blocked", 0)
        exp_total_tasks = exp_sent + exp_failed  # Expected total DM tasks to be created

        our_total_tasks = our_stats_imm.get("sent", 0) + our_stats_imm.get("queued", 0) + our_stats_imm.get("failed", 0)
        our_dups = our_stats_imm.get("duplicates_blocked", 0)

        diff_tasks = our_total_tasks - exp_total_tasks
        diff_dups = our_dups - exp_dups

        print(f"{'Total DM Tasks':<20} | {str(exp_total_tasks):<18} | {str(our_total_tasks):<20} | {str(diff_tasks):<10}")
        print(f"{'duplicates_blocked':<20} | {str(exp_dups):<18} | {str(our_dups):<20} | {str(diff_dups):<10}")
        print("-" * 75)

    if lt_proc:
        lt_proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
