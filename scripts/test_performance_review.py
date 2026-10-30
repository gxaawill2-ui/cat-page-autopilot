import datetime as dt
import unittest
import performance_review as r
class ReviewSafety(unittest.TestCase):
    def test_three_day_boundaries_are_taipei_and_never_current_partial_period(self):
        self.assertEqual(r.completed_period(dt.datetime(2026,10,30,8,tzinfo=r.base.TZ)),(dt.date(2026,10,27),dt.date(2026,10,29)))
        self.assertEqual(r.completed_period(dt.datetime(2026,11,2,8,tzinfo=r.base.TZ)),(dt.date(2026,10,30),dt.date(2026,11,1)))
    def test_missing_metrics_remain_missing_not_zero(self):
        out=r.row({"id":"1","created_time":"2026-10-29T01:30:00+0000"},dt.datetime(2026,10,30,8,tzinfo=r.base.TZ))
        self.assertIsNone(out["reactions"])
        self.assertIsNone(out["reach"])
        self.assertIsNone(out["share_rate"])
    def test_real_zero_is_preserved_but_boolean_not_a_metric(self):
        self.assertEqual(r.count(0),0)
        self.assertIsNone(r.count(True))
