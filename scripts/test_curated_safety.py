import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import meta_native_schedule as n

class CuratedSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patch=patch.object(n,'ROOT',self.root);self.patch.start()
        n.base.write(self.root/'state/policy.json',dict(mode='live',page_id=n.PAGE,timezone='Asia/Taipei',daily_limit=4))
        self.at=dt.datetime(2026,11,1,18,0,tzinfo=n.TZ)
        self.q=dict(page_id=n.PAGE,slot='2026-11-01T18:00',caption='Original selected cat story',language='en',image_sha256='a'*64,image_url=n.base.ASSET_BASE+'a'*64+'.jpg',source_png_sha256='b'*64,curated_id='selected-test',image_qa=True,source='ChatGPT original; user-selected')
        self.reserve(self.q)
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def reserve(self,q):n.base.write(self.root/'state/curated_reservations'/(q['curated_id']+'.json'),dict(q,status='reserved'))
    def empty(self):return dict(posts=[],scheduled_posts=[])
    def test_exact_selected_original_can_use_custom_time(self):n.validate(self.q,self.at-dt.timedelta(hours=2))
    def test_caption_tamper_fails(self):
        self.q['caption']='changed'
        with self.assertRaises(ValueError):n.validate(self.q,self.at-dt.timedelta(hours=2))
    def test_image_tamper_fails(self):
        self.q['image_sha256']='c'*64
        with self.assertRaises(ValueError):n.validate(self.q,self.at-dt.timedelta(hours=2))
    def test_custom_time_without_reservation_fails(self):
        del self.q['curated_id']
        with self.assertRaises(ValueError):n.validate(self.q,self.at-dt.timedelta(hours=2))
    def test_89_minutes_remote_fails(self):
        lists=self.empty();lists['scheduled_posts']=[dict(id='existing',scheduled_publish_time=int((self.at-dt.timedelta(minutes=89)).timestamp()))]
        with self.assertRaises(ValueError):n.remote_guard(self.q,self.at,4,lists)
    def test_exact_90_minutes_is_allowed(self):
        lists=self.empty();lists['scheduled_posts']=[dict(id='existing',scheduled_publish_time=int((self.at-dt.timedelta(minutes=90)).timestamp()))]
        n.remote_guard(self.q,self.at,4,lists)
    def test_own_reservation_does_not_block_itself(self):n.remote_guard(self.q,self.at,4,self.empty())
    def test_three_other_reserved_and_one_remote_block_autopilot(self):
        for i,slot in enumerate(('11:00','15:00')):
            self.reserve(dict(self.q,slot='2026-11-01T'+slot,curated_id='other-'+str(i),caption='other '+str(i)))
        lists=self.empty();lists['scheduled_posts']=[dict(id='existing',scheduled_publish_time=int(self.at.replace(hour=9,minute=30).timestamp()))]
        candidate=dict(slot='2026-11-01T12:30',caption='autopilot')
        with self.assertRaises(ValueError):n.remote_guard(candidate,n.stamp(candidate['slot']),4,lists)
    def test_unknown_native_attempt_replaces_not_erases_reservation(self):
        n.base.write(n.record_file(self.q),dict(slot=self.q['slot'],status='schedule_armed_unknown'))
        rows=list(n.entries());self.assertEqual(len(rows),1);self.assertEqual(rows[0]['status'],'schedule_armed_unknown')
        with self.assertRaises(ValueError):n.validate(self.q,self.at-dt.timedelta(hours=2))
    def test_completed_native_not_double_counted_as_reservation(self):
        n.base.write(n.record_file(self.q),dict(slot=self.q['slot'],status='scheduled_api_verified',meta_post_id='post'))
        self.assertEqual(len(list(n.entries())),1)
    def test_reserved_original_blocks_image_reuse_in_standard_queue(self):
        q=dict(self.q,slot='2026-11-02T19:30');del q['curated_id']
        with self.assertRaises(ValueError):n.validate(q,self.at)
    def test_past_curated_slot_cannot_be_backfilled(self):
        with self.assertRaises(ValueError):n.validate(self.q,self.at+dt.timedelta(minutes=1))
