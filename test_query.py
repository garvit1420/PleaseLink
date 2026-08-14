import asyncio
import time
from app.database import Database

async def main():
    db = Database('data/linkplease.db')
    await db.connect()
    print("CURRENT TIME:", time.time())
    
    # Check what is in the table
    cursor = await db._conn.execute("SELECT id, status, next_retry_at FROM dm_tasks")
    rows = await cursor.fetchall()
    print("ALL ROWS:", [dict(r) for r in rows])
    
    # Check the query
    t = time.time()
    print("QUERY TIME:", t)
    cursor = await db._conn.execute(
        """SELECT id, rule_id, user_id, comment_id, dm_message,
                  idempotency_key, retry_count, next_retry_at
           FROM   dm_tasks
           WHERE  status = 'queued'
             AND  (next_retry_at IS NULL OR next_retry_at <= ?)
           ORDER BY next_retry_at ASC, id ASC
           LIMIT 1""",
        (t,)
    )
    res = await cursor.fetchone()
    print("RESULT:", dict(res) if res else None)
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(main())
