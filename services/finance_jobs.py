"""Restart-safe maintenance. Every checkpoint and payment is committed atomically."""
import asyncio
from database import get_connection
from services.finance import now_utc,advance_market,advance_loans,refresh_crypto

def tick(path):
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE');now=now_utc();advance_market(c,now)
        for user in c.execute('SELECT user_id FROM finance_accounts').fetchall():advance_loans(c,user[0],now)
        c.commit()

async def run(path,application):
    from services.supabase_sync import queue_snapshot_sync
    while True:
        try:
            await asyncio.to_thread(tick,path)
            await asyncio.to_thread(refresh_crypto,path)
            queue_snapshot_sync(application)
        except asyncio.CancelledError:raise
        except Exception as error:
            print(f'Financial maintenance will retry: {type(error).__name__}',flush=True)
        await asyncio.sleep(60)
