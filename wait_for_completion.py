import time
import httpx
import json
import sys

URL = "https://pleaselink.onrender.com"
MOCK_API = "https://pseudogram-api.onrender.com/v1/simulate"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"

if len(sys.argv) > 1:
    run_id = sys.argv[1]
else:
    print("Run ID required")
    sys.exit(1)

print(f"Waiting for queue to drain on {URL} for run {run_id}...")

while True:
    try:
        r = httpx.get(f"{URL}/stats", timeout=10.0)
        stats = r.json()
        print(f"[{time.strftime('%X')}] Stats: {stats}")
        if stats.get("queued", 0) == 0 and (stats.get("sent", 0) > 0 or stats.get("failed", 0) > 0):
            break
    except Exception as e:
        print(f"Error fetching stats: {e}")
    time.sleep(30)

print("\nQueue is completely drained! Fetching final truth and comparing...")
try:
    r_truth = httpx.get(f"{MOCK_API}/{run_id}/truth", headers={"X-API-Key": API_KEY})
    truth_data = r_truth.json()
    expected = truth_data.get("expected_stats", {})
    
    exp_sent = expected.get("sent", 0)
    exp_failed = expected.get("failed", 0)
    exp_dups = expected.get("duplicates_blocked", 0)
    exp_total_tasks = exp_sent + exp_failed

    our_total_tasks = stats.get("sent", 0) + stats.get("queued", 0) + stats.get("failed", 0)
    our_dups = stats.get("duplicates_blocked", 0)

    diff_tasks = our_total_tasks - exp_total_tasks
    diff_dups = our_dups - exp_dups

    print("\n========================================================")
    print("         FINAL OFFICIAL GROUND TRUTH REPORT             ")
    print("========================================================")
    print(f"Run ID: {run_id}")
    print(f"Public Webhook URL: {URL}/webhook\n")
    print("SIDE-BY-SIDE COMPUTED DIFFERENCES:")
    print(f"{'Field':<20} | {'Official Expected':<18} | {'Our /stats (Total)':<20} | {'Difference':<10}")
    print("-" * 75)
    print(f"{'Total DM Tasks':<20} | {str(exp_total_tasks):<18} | {str(our_total_tasks):<20} | {str(diff_tasks):<10}")
    print(f"{'duplicates_blocked':<20} | {str(exp_dups):<18} | {str(our_dups):<20} | {str(diff_dups):<10}")
    print("-" * 75)
    print(f"{'Sent DMs':<20} | {str(exp_sent):<18} | {str(stats.get('sent', 0)):<20} | {str(stats.get('sent', 0) - exp_sent):<10}")
    print(f"{'Failed DMs':<20} | {str(exp_failed):<18} | {str(stats.get('failed', 0)):<20} | {str(stats.get('failed', 0) - exp_failed):<10}")

except Exception as e:
    print(f"Error fetching truth: {e}")
