import hmac
import hashlib
import base64

raw_body = b'{"event_id": "evt_c0a457c0c8b745", "event_type": "comment.created", "sent_at": "2026-08-18T12:01:07.858308+00:00", "data": {"comment_id": "cmt_48fcf655f0", "post_id": "post_c70fe50f16", "text": "wow just wow", "created_at": "2026-08-18T12:01:07.858330+00:00", "from": {"user_id": "usr_115a63350e", "username": "meera.953"}}}'
received_sha256 = "4a53b7b6e58c1ea487653ee1f59e2e58c18a29976e9afd1f800c4e0d6308cce9"

print(f"received_sha256 length: {len(received_sha256)}")

full_key = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20.c33eb167db294d992dc9"
part_before_dot = "Z2JnYXJ2aXQ3OEBnbWFpbC5jb20"
part_after_dot = "c33eb167db294d992dc9"
# Fix base64 padding before decoding
decoded_email = base64.b64decode(part_before_dot + "===").decode('utf-8')

print(f"Decoded email: {decoded_email}")

keys_to_test = {
    "1. The full API key string": full_key.encode(),
    "2. Only the part after the dot": part_after_dot.encode(),
    "3. Only the part before the dot": part_before_dot.encode(),
    "4. The base64-DECODED first part (email)": decoded_email.encode(),
}

try:
    full_decoded = base64.b64decode(full_key + "===")
    keys_to_test["5. The full key but base64-decoded entirely"] = full_decoded
except Exception as e:
    print(f"Could not base64 decode the full key: {e}")

found = False
for desc, key_bytes in keys_to_test.items():
    computed = hmac.new(key_bytes, raw_body, hashlib.sha256).hexdigest()
    if computed == received_sha256:
        print(f"\n[!] MATCH FOUND!")
        print(f"    Description: {desc}")
        print(f"    Key used: {key_bytes}")
        found = True

if not found:
    print("\nNo keys matched.")
