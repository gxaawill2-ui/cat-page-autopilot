"""CAS-fenced transitions. Caller MUST CAS-save returned state before any effect."""
import datetime as dt,uuid
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Asia/Taipei')
def arm(d,owner):
 if d.get('status')!='reserved' or d.get('dispatch_started_at'):raise ValueError('DISPATCH_ALREADY_OR_UNKNOWN')
 slot=dt.datetime.fromisoformat(d['slot']).replace(tzinfo=TZ)
 if slot.date()!=dt.datetime.now(TZ).date():raise ValueError('EXPIRED_SLOT')
 return dict(d,status='publishing',dispatch_owner=owner,dispatch_nonce=uuid.uuid4().hex,dispatch_started_at=dt.datetime.now(TZ).isoformat(),dispatch_protocol=2)
def expire(d):
 if d.get('status')!='reserved' or d.get('dispatch_started_at') or d.get('dispatch_protocol')!=2:raise ValueError('CANNOT_PROVE_NOT_DISPATCHED')
 if dt.datetime.fromisoformat(d['slot']).date()>=dt.datetime.now(TZ).date():raise ValueError('NOT_EXPIRED')
 return dict(d,status='not_published',closed_at=dt.datetime.now(TZ).isoformat(),close_reason='expired fenced reservation; no dispatch CAS permitted after closure')
# Legacy publishing, unknown response, and interrupted dispatched calls NEVER expire automatically.
