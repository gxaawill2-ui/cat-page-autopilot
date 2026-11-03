import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import performance_review as r

class OwnerExclusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.p=patch.object(r,'ROOT',self.root);self.p.start()
        r.base.write(self.root/'state/engagement_exclusions.json',{'known_owner_reactions':{'p':{'count':1}}})
    def tearDown(self):self.p.stop();self.tmp.cleanup()
    def test_owner_only_like_is_not_external_growth(self):
        out=r.external_reactions('p',1)
        self.assertEqual(out['reactions_after_known_owner_exclusion'],0)
        self.assertEqual(out['verified_external_reactions'],0)
    def test_unavailable_total_stays_na(self):
        self.assertIsNone(r.external_reactions('p',None)['verified_external_reactions'])
    def test_other_positive_reactions_without_identities_are_not_confirmed(self):
        self.assertIsNone(r.external_reactions('p',3)['verified_external_reactions'])
        self.assertEqual(r.external_reactions('p',3)['reactions_after_known_owner_exclusion'],2)
    def test_missing_exclusion_does_not_make_positive_likes_external(self):
        self.assertIsNone(r.external_reactions('other',1)['verified_external_reactions'])
