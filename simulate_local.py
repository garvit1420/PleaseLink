import asyncio
import httpx
import uuid
import hmac
import hashlib
from app.config import API_KEY

async def main():
    async with httpx.AsyncClient() as client:
        print("Creating rule 'LINK'...")
        await client.post("http://localhost:8000/rules", json={
            "keyword": "LINK",
            "dm_message": "Here is the link!"
        })
        
        def send_event(payload):
            # Sign the payload for Part B
            raw_body = httpx.Request('POST', 'http://localhost:8000/webhook', json=payload).read()
            sig = "sha256=" + hmac.new(API_KEY.encode(), raw_body, hashlib.sha256).hexdigest()
            return client.post("http://localhost:8000/webhook", content=raw_body, headers={
                "X-PseudoGram-Signature": sig,
                "Content-Type": "application/json"
            })
            
        print("Sending event 1: Normal comment matching LINK (user_100)")
        event_id_1 = str(uuid.uuid4())
        user_1 = "user_100"
        comment_id_1 = "comm_1"
        await send_event({
            "event_id": event_id_1,
            "event_type": "comment.created",
            "data": {
                "comment_id": comment_id_1,
                "text": "pls give LINK",
                "from": {"user_id": user_1, "username": "alice"}
            }
        })
        
        print("Sending event 2: Exact duplicate of event 1 (same event_id)")
        await send_event({
            "event_id": event_id_1, # Same event ID
            "event_type": "comment.created",
            "data": {
                "comment_id": comment_id_1,
                "text": "pls give LINK",
                "from": {"user_id": user_1, "username": "alice"}
            }
        })

        print("Sending event 3: comment.deleted arrives BEFORE comment.created")
        event_id_2 = str(uuid.uuid4())
        event_id_3 = str(uuid.uuid4())
        comment_id_2 = "comm_2"
        user_2 = "user_200"
        
        # Deletion arrives first
        await send_event({
            "event_id": event_id_3,
            "event_type": "comment.deleted",
            "data": {"comment_id": comment_id_2}
        })
        # Then creation
        await send_event({
            "event_id": event_id_2,
            "event_type": "comment.created",
            "data": {
                "comment_id": comment_id_2,
                "text": "LINK",
                "from": {"user_id": user_2, "username": "bob"}
            }
        })

        print("Sending event 4: New comment from user_100 for 'LINK' (should be dedup blocked)")
        event_id_4 = str(uuid.uuid4())
        comment_id_4 = "comm_4"
        await send_event({
            "event_id": event_id_4,
            "event_type": "comment.created",
            "data": {
                "comment_id": comment_id_4,
                "text": "another LINK please",
                "from": {"user_id": user_1, "username": "alice"}
            }
        })
        
        print("Waiting 15 seconds for DM Sender and Reconciler...")
        await asyncio.sleep(15)
        
        print("Fetching stats...")
        r = await client.get("http://localhost:8000/stats")
        print("STATS:", r.json())

if __name__ == "__main__":
    asyncio.run(main())
