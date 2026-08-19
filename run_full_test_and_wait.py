import subprocess
import os
import sys

env = os.environ.copy()
env["SIM_COUNT"] = "500"
env["PUBLIC_URL"] = "https://pleaselink.onrender.com"

print("Starting official test...")
proc = subprocess.Popen(["python", "run_official_test.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

run_id = None
for line in proc.stdout:
    sys.stdout.write(line)
    if "Run ID: run_" in line:
        run_id = line.split("Run ID: ")[1].strip()

proc.wait()

if not run_id:
    print("Failed to find run_id from output.")
    sys.exit(1)

print(f"\nProceeding to wait for completion with run_id: {run_id}")
subprocess.run(["python", "wait_for_completion.py", run_id], env=env)
