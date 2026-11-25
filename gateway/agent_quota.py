"""Atomic daily free turns in EnzyMind's own database; no provider keys."""
import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def period(now=None):
    timezone = os.getenv('ENZYMIND_AGENT_QUOTA_TIMEZONE', 'Asia/Shanghai')
    current = datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo(timezone))
    reset = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return current.date().isoformat(), reset.isoformat(), timezone


def reconcile(db, now=None):
    now = time.time() if now is None else now
    # Keep successful charges independent of conversation deletion. Reservations
    # are released after failure, cancellation or a worker's expired lease.
    db.execute("UPDATE agent_usage SET state='done' WHERE state='reserved' AND turn_id IN (SELECT id FROM turns WHERE status='completed')")
    db.execute("DELETE FROM agent_usage WHERE created<? OR (state='reserved' AND NOT EXISTS(SELECT 1 FROM turns t WHERE t.id=agent_usage.turn_id AND t.status IN ('queued','running') AND t.lease_expires>? AND t.created>?))", (now-172800, now, now-7200))


def usage(db, owner, now=None):
    day, reset, timezone = period(now)
    rows = dict(db.execute('SELECT state,count(*) FROM agent_usage WHERE owner=? AND quota_date=? GROUP BY state', (owner, day)).fetchall())
    used = sum(rows.values())
    limit = max(1, int(os.getenv('ENZYMIND_AGENT_DAILY_LIMIT', '10')))
    return {'used': used, 'reserved': rows.get('reserved', 0), 'limit': limit,
            'remaining': max(0, limit-used), 'date': day, 'resets_at': reset, 'timezone': timezone}


def reserve(db, owner, turn_id, now):
    reconcile(db, now)
    current = usage(db, owner, now)
    if current['remaining'] == 0:
        raise HTTPException(402, {'code': 'daily_limit', 'message': 'Today’s free conversations are used. Add your DeepSeek API key to continue.', 'quota': current})
    db.execute("INSERT INTO agent_usage(turn_id,owner,quota_date,state,created) VALUES(?,?,?,'reserved',?)", (turn_id, owner, current['date'], now))
