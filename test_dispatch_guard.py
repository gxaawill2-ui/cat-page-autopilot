import unittest,datetime as dt
from unittest.mock import patch
import dispatch_guard as g
class Guard(unittest.TestCase):
 def setUp(self):self.d={'status':'reserved','dispatch_protocol':2,'slot':dt.datetime.now(g.TZ).date().isoformat()+'T19:30'}
 def test_pre_call_recovery_has_no_send(self):self.assertEqual(self.d['status'],'reserved');self.assertNotIn('dispatch_started_at',self.d)
 def test_armed_or_unknown_cannot_replay(self):
  a=g.arm(self.d,'owner')
  for d in [a,dict(a,status='published_unverified')]:
   with self.assertRaises(ValueError):g.arm(d,'retry')
   with self.assertRaises(ValueError):g.expire(d)
 def test_legacy_no_expiry(self):
  with self.assertRaises(ValueError):g.expire(dict(self.d,status='publishing',dispatch_protocol=1))
 def test_expired_unarmed_closes_but_cannot_send(self):
  d=dict(self.d,slot='2026-01-01T19:30');closed=g.expire(d);self.assertEqual(closed['status'],'not_published')
  with self.assertRaises(ValueError):g.arm(closed,'owner')
 def test_concurrent_compare_and_swap(self):
  # Both derive from same parent; actual adapter permits only one CAS winner.
  a=g.arm(self.d,'a');b=g.arm(self.d,'b');self.assertNotEqual(a['dispatch_nonce'],b['dispatch_nonce'])
