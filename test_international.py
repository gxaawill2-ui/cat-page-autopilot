import unittest,argparse,tempfile,json
from pathlib import Path
from unittest.mock import patch
import international as i,catflow as f
class InternationalTests(unittest.TestCase):
 def test_week1_and_week2(self):
  self.assertEqual(i.plan('2026-10-26T12:30')['language'],'zh-Hant')
  self.assertEqual(i.plan('2026-10-26T19:30')['target_markets'],['US','PH'])
  self.assertEqual(i.plan('2026-11-03T19:30')['language'],'ja')
  self.assertEqual(i.plan('2026-11-06T19:30')['language'],'ja')
 def test_no_extra_slots_or_excluded_markets(self):
  import datetime
  plans=[i.plan((datetime.date(2026,10,26)+datetime.timedelta(days=d)).isoformat()+'T'+t) for d in range(14) for t in ['12:30','19:30']]
  self.assertEqual(len(plans),28);self.assertEqual(sum(p['language']=='ja' for p in plans),2)
  self.assertFalse(any('ID' in p['target_markets'] for p in plans))
 def test_missing_reach_not_invented(self):
  self.assertIsNone(i.measures({'reactions':1,'comments':0,'shares':0})['engagement_per_1000_reach'])
  self.assertEqual(i.measures({'reach':100,'reactions':1,'comments':0,'shares':1})['engagement_per_1000_reach'],20)
 def test_prepare_language_survives_without_facebook(self):
  original=f.ROOT
  with tempfile.TemporaryDirectory() as tmp:
   f.ROOT=Path(tmp);caption=Path(tmp)/'caption.txt';caption.write_text('My calendar says work. My cat says lap time.')
   image=next((original/'docs/assets').glob('*.jpg'))
   a=argparse.Namespace(image=str(image),caption=str(caption),topic='lap time',style='fixture',caption_type='short_humor',source='V30 original fixture; NOT FOR REPUBLISH',sources=[],language='en',target_markets=['US','PH'],experiment_id='intl-20261026-14d')
   try:
    d=f.prepare(a);self.assertEqual(d['language'],'en');self.assertEqual(d['target_markets'],['US','PH']);self.assertLess(d['bytes'],4000000)
   finally:f.ROOT=original
 def test_global_unknown_blocks_new_content(self):
  original=f.ROOT
  with tempfile.TemporaryDirectory() as tmp:
   f.ROOT=Path(tmp)
   try:
    f.write(f.ROOT/'state/policy.json',{'mode':'live'})
    f.write(f.ROOT/'state/posts/old.json',{'key':'old','caption_sha256':'old','image_sha256':'old','slot':'other','status':'publishing','reserved_at':f.now()})
    d=f.ROOT/'draft.json';f.write(d,{'key':'new','page_id':f.PAGE,'caption_sha256':'new','image_sha256':'new','image_url':'unused'})
    with self.assertRaisesRegex(ValueError,'UNRESOLVED_PUBLICATION'):f.reserve(argparse.Namespace(draft=d,slot=f.now()[:10]+'T19:30',purpose='regular',durable=False))
   finally:f.ROOT=original
if __name__=='__main__':unittest.main()
