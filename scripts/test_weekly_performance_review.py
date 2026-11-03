import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import weekly_performance_review as w


class WeeklyReviewSafety(unittest.TestCase):
    def test_cutoff_taipei_boundary_and_delayed_runner(self):
        self.assertIsNone(w.due_cutoff(dt.datetime(2026, 11, 1, 11, 59, tzinfo=dt.timezone.utc)))
        self.assertEqual(w.due_cutoff(dt.datetime(2026, 11, 1, 12, tzinfo=dt.timezone.utc)), w.FIRST_CUTOFF)
        self.assertEqual(w.due_cutoff(dt.datetime(2026, 11, 3, 8, tzinfo=w.base.TZ)), w.FIRST_CUTOFF)
        self.assertEqual(w.due_cutoff(dt.datetime(2026, 11, 8, 20, tzinfo=w.base.TZ)).date(), dt.date(2026, 11, 8))

    def test_known_review_rerun_never_calls_api(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'records/reviews/weekly-2026-11-01.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            with patch.object(w, 'ROOT', Path(d)), patch.object(w.native, 'api') as api:
                w.run(dt.datetime(2026, 11, 3, 8, tzinfo=w.base.TZ))
                api.assert_not_called()

    def test_missing_token_and_wrong_page_stop(self):
        with tempfile.TemporaryDirectory() as d, patch.object(w, 'ROOT', Path(d)):
            with patch.dict(os.environ, {}, clear=True), patch.object(w.native, 'api') as api:
                with self.assertRaises(ValueError): w.run(w.FIRST_CUTOFF)
                api.assert_not_called()
            with patch.dict(os.environ, {'META_PAGE_ACCESS_TOKEN': 'fixture'}), patch.object(w.native, 'api', return_value={'id': 'wrong'}):
                with self.assertRaises(ValueError): w.run(w.FIRST_CUTOFF)

    def test_permission_fallback_filters_drafts_and_window_edges(self):
        end = w.FIRST_CUTOFF
        posts = [
            {'id': 'a', 'created_time': end.isoformat(), 'is_published': True},
            {'id': 'b', 'created_time': (end-dt.timedelta(hours=1)).isoformat(), 'is_published': False},
            {'id': 'c', 'created_time': (end-dt.timedelta(hours=2)).isoformat(), 'is_published': True}]
        with patch.object(w.native, 'api', side_effect=[w.native.Rejected('permission denied'), {'data': posts}]) as api:
            out, errors = w.inventory('fixture', end-dt.timedelta(days=7), end)
            self.assertEqual([p['id'] for p in out], ['c'])
            self.assertEqual(len(errors), 1)
            self.assertEqual(api.call_args_list[1].args[2]['fields'], w.BASIC_FIELDS)

    def test_incomplete_inventory_never_becomes_zero(self):
        with patch.object(w.native, 'api', return_value={'data': [], 'paging': {'next': 'unused-url'}}):
            with self.assertRaises(ValueError): w.inventory('fixture', w.FIRST_CUTOFF-dt.timedelta(days=7), w.FIRST_CUTOFF)

    def test_real_report_only_gets_and_keeps_missing_attribution(self):
        now = dt.datetime(2026, 11, 3, 8, tzinfo=w.base.TZ)
        def api(path, token, params):
            if path == 'me': return {'id': w.base.PAGE_ID, 'followers_count': 0}
            self.assertEqual(path, w.base.PAGE_ID+'/posts')
            return {'data': [{'id': 'fixture_post', 'created_time': '2026-10-31T01:30:00+0000', 'is_published': True}]}
        with tempfile.TemporaryDirectory() as d, patch.object(w, 'ROOT', Path(d)), patch.dict(os.environ, {'META_PAGE_ACCESS_TOKEN': 'fixture'}), patch.object(w.native, 'api', side_effect=api), patch.object(w.base, 'persist') as persist:
            w.run(now)
            out = json.loads((Path(d)/'records/reviews/weekly-2026-11-01.json').read_text())
            self.assertEqual(out['facebook_write_calls'], 0)
            self.assertEqual(out['ai_calls'], 0)
            self.assertIsNone(out['current_window']['posts'][0]['verified_external_reactions'])
            self.assertIsNone(out['current_window']['non_follower_reach'])
            self.assertFalse(out['same_age_comparison_available'])
            persist.assert_called_once()


if __name__ == '__main__':
    unittest.main()
