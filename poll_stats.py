import urllib.request
import json
import time

URL = "https://pleaselink.onrender.com"

while True:
    r = urllib.request.urlopen(f"{URL}/stats")
    s = json.loads(r.read().decode())
    print(f"Live stats: {s}")
    if s.get("queued", 0) == 0 and s.get("sent", 0) > 0:
        print("Queue fully drained!")
        break
    time.sleep(5)
