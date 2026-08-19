import hmac
import hashlib
import json

API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
raw_body_bytes = b'{"event_id": "evt_67339bd6411646", "event_type": "comment.created", "sent_at": "2026-08-18T11:24:07.218705+00:00", "data": {"comment_id": "cmt_b2598604f6", "post_id": "post_4b12372703", "text": "where do you shoot this", "created_at": "2026-08-18T11:24:07.218710+00:00", "from": {"user_id": "usr_4e71399b7a", "username": "nikhil.72"}}}'

expected_hmac = "bbc9cf5c7e6f09b37d68ba2adbbc2ad70db46ed115ac8aa5029bf86df16559a0"

payload_dict = json.loads(raw_body_bytes.decode())

# Try different combinations of keys and separators
def check(key_str, sep_item, sep_dict, test_payload=payload_dict):
    try:
        body_str = json.dumps(test_payload, separators=(sep_item, sep_dict))
        h = hmac.new(key_str.encode(), body_str.encode(), hashlib.sha256).hexdigest()
        if h == expected_hmac:
            print(f"MATCH! Key: {key_str}, sep: ({repr(sep_item)}, {repr(sep_dict)})")
            print(f"Body: {body_str}")
            return True
    except Exception:
        pass
    return False

separators_to_test = [
    (',', ':'),
    (', ', ': '),
    (',', ': '),
    (', ', ':'),
]

keys_to_test = [
    API_KEY,
    API_KEY.split(".")[1],
    API_KEY.encode('utf-8').hex(),
]

found = False
for key in keys_to_test:
    for sep_item, sep_dict in separators_to_test:
        if check(key, sep_item, sep_dict):
            found = True

# What if keys were sorted?
def check_sorted(key_str, sep_item, sep_dict):
    body_str = json.dumps(payload_dict, separators=(sep_item, sep_dict), sort_keys=True)
    h = hmac.new(key_str.encode(), body_str.encode(), hashlib.sha256).hexdigest()
    if h == expected_hmac:
        print(f"MATCH SORTED! Key: {key_str}, sep: ({repr(sep_item)}, {repr(sep_dict)})")
        return True
    return False

for key in keys_to_test:
    for sep_item, sep_dict in separators_to_test:
        if check_sorted(key, sep_item, sep_dict):
            found = True

if not found:
    print("No match found with standard JSON variations.")
