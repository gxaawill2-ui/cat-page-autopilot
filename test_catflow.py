import argparse, json, tempfile, unittest
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

if __name__=='__main__':unittest.main()
