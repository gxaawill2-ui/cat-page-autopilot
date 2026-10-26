import unittest,argparse,tempfile
from pathlib import Path
from unittest.mock import patch
import catflow as f,international as i
class Frequency(unittest.TestCase):
 def test_new_slots(self):
  self.assertEqual(i.plan('2026-10-27T09:30')['language'],'en')
  self.assertEqual(i.plan('2026-10-27T16:30')['language'],'zh-Hant')
 def test_four_allowed_fifth_blocked(self):
  with tempfile.TemporaryDirectory() as t,patch.object(f,'ROOT',Path(t)),patch.object(f,'url_check',return_value={'http_status':200}):
   f.write(f.ROOT/'state/policy.json',{'mode':'live','daily_limit':4,'acceptance_task_id':'test'})
   for n in range(5):
    d={'key':str(n),'page_id':f.PAGE,'caption_sha256':str(n),'image_sha256':str(n),'image_url':'unused'}
    p=f.ROOT/'draft.json';f.write(p,d)
    a=argparse.Namespace(draft=p,slot=f.now()[:10]+'T'+str(n),purpose='acceptance',task_id='test',durable=False)
    if n==4:
     with self.assertRaisesRegex(ValueError,'DAILY_LIMIT'):f.reserve(a)
    else:
     f.reserve(a);d=f.read(f.ROOT/'state/posts'/f'{n}.json');d['status']='verified';f.write(f.ROOT/'state/posts'/f'{n}.json',d)
