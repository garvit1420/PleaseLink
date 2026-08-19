import hmac
import hashlib

API_KEY = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
raw_body = b'{"event_id": "evt_67339bd6411646", "event_type": "comment.created", "sent_at": "2026-08-18T11:24:07.218705+00:00", "data": {"comment_id": "cmt_b2598604f6", "post_id": "post_4b12372703", "text": "where do you shoot this", "created_at": "2026-08-18T11:24:07.218710+00:00", "from": {"user_id": "usr_4e71399b7a", "username": "nikhil.72"}}}'

expected = hmac.new(API_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
print("Expected:", expected)
print("Received:", "bbc9cf5c7e6f09b37d68ba2adbbc2ad70db46ed115ac8aa5029bf86df16559a0")

# Check if maybe they sign without spaces?
raw_body_no_spaces = raw_body.replace(b': ', b':').replace(b', ', b',')
expected_no_spaces = hmac.new(API_KEY.encode(), raw_body_no_spaces, hashlib.sha256).hexdigest()
print("Expected no spaces:", expected_no_spaces)

# Check if maybe the proxy adds a newline?
expected_newline = hmac.new(API_KEY.encode(), raw_body + b'\n', hashlib.sha256).hexdigest()
print("Expected with newline:", expected_newline)

# Check if they used only the second half of the API key?
second_half = API_KEY.split(".")[1]
expected_second_half = hmac.new(second_half.encode(), raw_body, hashlib.sha256).hexdigest()
print("Expected second half:", expected_second_half)
