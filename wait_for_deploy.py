import urllib.request
import urllib.error
import time

url = "https://pleaselink.onrender.com/stats"
print("Waiting for Render to finish deploying...")

# Sleep for 60 seconds initially to give Render time to take down the old instance
time.sleep(60)

while True:
    req = urllib.request.Request(url)
    try:
        response = urllib.request.urlopen(req)
        print("Success! Endpoint returned 200. The new version is live.")
        break
    except Exception as e:
        print(f"Got exception {e}. Retrying...")
    
    time.sleep(10)
