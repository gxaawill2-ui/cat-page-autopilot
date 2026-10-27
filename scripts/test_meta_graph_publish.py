import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import meta_graph_publish as p

class OfficialMetaSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = p.ROOT
        p.ROOT = Path(self.tmp.name)
        self.day = dt.datetime.now(p.TZ).date().isoformat()
        self.now = dt.datetime.fromisoformat(self.day + "T12:40:00+08:00")
        self.image_sha = "a"*64
        self.q = {"page_id": p.PAGE_ID, "slot": self.day+"T12:30",
                  "caption": "新原創貓咪文案", "language": "zh-Hant",
                  "image_sha256": self.image_sha,
                  "image_url": p.ASSET_BASE+self.image_sha+".jpg"}
        p.write(p.queue_path(self.day, "12:30"), self.q)
    def tearDown(self):
        p.ROOT = self.root
        self.tmp.cleanup()
    def test_no_queue_no_publish(self):
        self.assertEqual(p.run("09:30", now=self.now), "skipped")
    def test_disabled_means_no_graph_call(self):
        with patch.dict("os.environ", {"META_PUBLISH_ENABLED": "false", "META_PAGE_ACCESS_TOKEN": "fake"}):
            with patch.object(p, "graph", side_effect=AssertionError("must not call Meta")):
                self.assertEqual(p.run("12:30", now=self.now), "skipped")
    def test_dry_run_means_no_graph_call(self):
        with patch.object(p, "graph", side_effect=AssertionError("must not call Meta")):
            self.assertEqual(p.run("12:30", dry_run=True, now=self.now), "dry-run")
    def test_stale_slot_no_publish(self):
        late=self.now + dt.timedelta(hours=2)
        self.assertEqual(p.run("12:30", now=late), "skipped")
    def test_old_caption_never_republished(self):
        p.write(p.ROOT/"state/posts/old.json", {"caption": self.q["caption"], "image_sha256": "b"*64})
        with self.assertRaisesRegex(ValueError, "Same old"):
            p.run("12:30", dry_run=True, now=self.now)
    def test_old_image_never_republished(self):
        p.write(p.ROOT/"state/posts/old.json", {"caption": "different", "image_sha256": self.image_sha})
        with self.assertRaisesRegex(ValueError, "Same old"):
            p.run("12:30", dry_run=True, now=self.now)
    def test_outcome_file_prohibits_replay(self):
        p.write(p.result_path(self.day, "12:30"), {"status":"armed_unknown_until_reconciled"})
        self.assertEqual(p.run("12:30", now=self.now), "skipped")
    def test_untrusted_url_rejected(self):
        self.q["image_url"]="https://other.example.com/cat.jpg"
        p.write(p.queue_path(self.day,"12:30"),self.q)
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            p.run("12:30",dry_run=True,now=self.now)
    def test_missing_token_no_publish(self):
        with patch.dict("os.environ", {"META_PUBLISH_ENABLED":"true"}, clear=True):
            with patch.object(p,"graph",side_effect=AssertionError("must not call Meta")):
                self.assertEqual(p.run("12:30",now=self.now),"skipped")

if __name__ == "__main__":
    unittest.main()
