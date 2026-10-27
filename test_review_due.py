import unittest,datetime as dt
from zoneinfo import ZoneInfo
from review_due import review_key
class Review(unittest.TestCase):
 def key(self,s):return review_key(dt.datetime.fromisoformat(s).replace(tzinfo=ZoneInfo('Asia/Taipei')))
 def test_boundaries(self):
  for s,k in [('2026-10-29T19:29',None),('2026-10-29T19:30','2026-10-29'),('2026-11-01T19:29','2026-10-29'),('2026-11-01T19:30','2026-11-01')]:self.assertEqual(self.key(s),k)
