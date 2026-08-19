import urllib.request
import json

URL = "https://pseudogram-api.onrender.com/v1/simulate/run_1d6dabdf51a4/truth"
API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"

req = urllib.request.Request(URL, headers={"X-API-Key": API_KEY})
truth = json.loads(urllib.request.urlopen(req).read().decode())

print(json.dumps(truth, indent=2))
