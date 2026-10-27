import argparse, datetime as dt, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import catflow as f

class PublishingGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old=f.ROOT; f.ROOT=Path(self.tmp.name)
        f.write(f.ROOT/'state/policy.json',{'mode':'draft','acceptance_task_id':'test'})
        self.d={'key':'key','page_id':f.PAGE,'caption':'新文案','caption_sha256':'text','image_sha256':'img','image_url':f.BASE+'assets/img.jpg'}
        self.path=f.ROOT/'draft.json';f.write(self.path,self.d)
        self.a=argparse.Namespace(draft=str(self.path),slot=f.now()[:10]+'T12:30',purpose='acceptance',task_id='test',durable=False)
        self.mock=patch.object(f,'url_check',return_value={'http_status':200});self.mock.start()
    def tearDown(self):self.mock.stop();f.ROOT=self.old;self.tmp.cleanup()
    def test_draft_mode_blocks_regular_run(self):
        self.a.purpose='regular'
        with self.assertRaisesRegex(ValueError,'DRAFT_GATE'):f.reserve(self.a)
    def test_wrong_page_is_blocked(self):
        self.d['page_id']='other';f.write(self.path,self.d)
        with self.assertRaisesRegex(ValueError,'Wrong'):f.reserve(self.a)
    def test_unknown_publication_cannot_be_repeated(self):
        f.reserve(self.a)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):f.reserve(self.a)
    def test_reused_image_different_caption_is_blocked(self):
        f.reserve(self.a);self.d.update(key='new',caption_sha256='newtext');f.write(self.path,self.d)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):f.reserve(self.a)
    def test_slot_is_atomic_before_publication(self):
        f.reserve(self.a);self.d.update(key='new',caption_sha256='newtext',image_sha256='newimg');f.write(self.path,self.d)
        with self.assertRaisesRegex(ValueError,'SLOT_RESERVED'):f.reserve(self.a)
    def test_daily_limit_includes_uncertain_outcomes(self):
        for i in range(2):f.write(f.ROOT/f'state/posts/{i}.json',dict(self.d,key=str(i),caption_sha256=str(i),image_sha256=str(i),slot=str(i),reserved_at=f.now(),status='publishing'))
        with self.assertRaisesRegex(ValueError,'DAILY_LIMIT'):f.reserve(self.a)
    def test_no_post_id_does_not_clear_pending_lock(self):
        f.reserve(self.a);result=f.ROOT/'result.txt';result.write_text('timeout')
        with self.assertRaisesRegex(ValueError,'No genuine'):f.receipt(argparse.Namespace(key='key',result=str(result),durable=False))
        self.assertEqual(f.read(f.ROOT/'state/posts/key.json')['status'],'publishing')
    def test_wrong_readback_caption_is_not_verified(self):
        f.reserve(self.a);p=f.ROOT/'state/posts/key.json';d=f.read(p);d['post_id']=f.PAGE+'_123';f.write(p,d)
        rows=f.ROOT/'rows.json';f.write(rows,[{'post_id':d['post_id'],'post_message':'wrong','full_picture':'https://example.com/image.jpg'}])
        with self.assertRaisesRegex(ValueError,'mismatch'):f.verify(argparse.Namespace(key='key',rows=str(rows),visual='passed',durable=False))

    def _legacy_with_quarantine(self, old_day):
        k='historical-unknown';old={
            'key':k,'page_id':f.PAGE,'slot':old_day+'T19:30','reserved_at':old_day+'T19:31:00+08:00',
            'status':'publishing','caption_sha256':'old-text','image_sha256':'old-image',
            'reconciliation':{'classification':'unknown','closure_allowed':False,'resend_allowed':False,
                              'evidence_record':'records/reconciliation/2026-10-27-legacy.json'}}
        f.write(f.ROOT/'state/posts/legacy.json',old)
        q={'version':1,'enabled':True,'mode':'scoped_legacy_quarantine',
           'quarantined':[dict(key=k,slot=old['slot'],caption_sha256='old-text',image_sha256='old-image',
                               status='unknown_not_closed',resend_allowed=False,
                               evidence_record='records/reconciliation/2026-10-27-legacy.json')]}
        f.write(f.ROOT/'state/legacy_quarantine.json',q)
        return old
    def test_exact_legacy_quarantine_allows_new_unique_day(self):
        yesterday=(dt.datetime.now(f.TZ).date()-dt.timedelta(days=1)).isoformat()
        old=self._legacy_with_quarantine(yesterday)
        self.assertTrue(f.quarantined_historical_pending(old,self.a.slot))
        self.assertEqual(f.reserve(self.a)['key'],'key')
        self.assertEqual(f.read(f.ROOT/'state/posts/legacy.json')['status'],'publishing')
    def test_same_day_unknown_still_blocks(self):
        today=dt.datetime.now(f.TZ).date().isoformat()
        old=self._legacy_with_quarantine(today)
        self.assertFalse(f.quarantined_historical_pending(old,self.a.slot))
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PUBLICATION'):f.reserve(self.a)
    def test_protocol2_unknown_never_quarantined(self):
        yesterday=(dt.datetime.now(f.TZ).date()-dt.timedelta(days=1)).isoformat()
        old=self._legacy_with_quarantine(yesterday)
        old['dispatch_protocol']=2;f.write(f.ROOT/'state/posts/legacy.json',old)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PUBLICATION'):f.reserve(self.a)
    def test_changed_hash_or_missing_config_never_quarantined(self):
        yesterday=(dt.datetime.now(f.TZ).date()-dt.timedelta(days=1)).isoformat()
        old=self._legacy_with_quarantine(yesterday)
        old['image_sha256']='tampered';f.write(f.ROOT/'state/posts/legacy.json',old)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PUBLICATION'):f.reserve(self.a)
        old['image_sha256']='old-image';f.write(f.ROOT/'state/posts/legacy.json',old)
        (f.ROOT/'state/legacy_quarantine.json').unlink()
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PUBLICATION'):f.reserve(self.a)
    def test_old_content_reuse_remains_forbidden(self):
        yesterday=(dt.datetime.now(f.TZ).date()-dt.timedelta(days=1)).isoformat()
        old=self._legacy_with_quarantine(yesterday)
        self.d['caption_sha256']=old['caption_sha256'];f.write(self.path,self.d)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):f.reserve(self.a)

if __name__=='__main__':unittest.main()
