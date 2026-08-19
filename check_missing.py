import urllib.request
import json

req = urllib.request.Request('https://pleaselink.onrender.com/stats')
print("Stats:", urllib.request.urlopen(req).read().decode())
