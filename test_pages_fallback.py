import unittest,urllib.error,datetime as dt
from unittest.mock import patch
import catflow
class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.d=catflow.read(catflow.ROOT/'records/drafts/18ab2e2f81b0d1c25726390650e966e6cbb35a6d92e09b4b3c03fea67853d5db.json')
  self.proof=catflow.read(catflow.ROOT/'records/pages-proofs'/ (self.d['key']+'.json'))
  self.proof['checked_at']=catflow.now()
 def check(self,p):
  with patch('catflow.url_check',side_effect=urllib.error.URLError('restricted')),patch('catflow.read',return_value=p):return catflow.release_check(self.d)
 def test_transport_uses_matching_evidence(self):self.assertEqual(self.check(self.proof)['sha256'],self.d['image_sha256'])
 def test_stale(self):
  self.proof['checked_at']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=2)).isoformat()
  with self.assertRaises(ValueError):self.check(self.proof)
 def test_wrong_sha(self):
  self.proof['sha256']='0'*64
  with self.assertRaises(ValueError):self.check(self.proof)
 def test_real_http_error_not_overridden(self):
  with patch('catflow.url_check',side_effect=urllib.error.HTTPError('url',404,'missing',{},None)):
   with self.assertRaises(urllib.error.HTTPError):catflow.release_check(self.d)
