import urllib.request
import json
req = urllib.request.Request('https://pleaselink.onrender.com/debug/query', data=json.dumps({"query": "SELECT * FROM rules"}).encode(), headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req).read().decode())
