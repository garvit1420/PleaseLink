import urllib.request
import json
req = urllib.request.Request('https://pleaselink.onrender.com/debug/query', data=json.dumps({"query": "SELECT status, count(*) as cnt FROM dm_tasks GROUP BY status"}).encode(), headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(req).read().decode())
