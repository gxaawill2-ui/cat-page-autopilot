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
        p.write(p.ROOT / "state/policy.json", {"mode":"live", "page_id":p.PAGE_ID,
            "timezone":"Asia/Taipei", "daily_limit":4})
    def tearDown(self):
        p.ROOT = self.root
        self.tmp.cleanup()
    def test_no_queue_no_publish(self):
        p.queue_path(self.day, "12:30").unlink()
        with patch.object(p, "graph", side_effect=AssertionError("must not call Meta")):
            self.assertEqual(p.run("12:30", now=self.now), "skipped")
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

    def test_draft_policy_blocks_even_with_switch_and_token(self):
        p.write(p.ROOT/"state/policy.json", {"mode":"draft"})
        with patch.dict("os.environ", {"META_PUBLISH_ENABLED":"true", "META_PAGE_ACCESS_TOKEN":"fake"}):
            with patch.object(p,"graph",side_effect=AssertionError("no Meta")):
                with self.assertRaisesRegex(ValueError,"POLICY_GATE"):
                    p.run("12:30",now=self.now)

    def test_old_unknown_same_slot_blocks_new_caption(self):
        p.write(p.ROOT/"state/posts/old.json", {"slot":self.q["slot"],"status":"publishing"})
        with self.assertRaisesRegex(ValueError,"SLOT_RESERVED"):
            p.run("12:30",dry_run=True,now=self.now)

    def test_cap_counts_old_and_new_unknown_attempts(self):
        policy=p.read(p.ROOT/"state/policy.json");policy["daily_limit"]=2
        p.write(p.ROOT/"state/policy.json",policy)
        p.write(p.ROOT/"state/posts/old.json",{"slot":self.day+"T09:30+08:00","status":"publishing"})
        p.write(p.ROOT/"state/meta_dispatch/old.json",{"slot":self.day+"T16:30","status":"armed_unknown_until_reconciled"})
        with self.assertRaisesRegex(ValueError,"DAILY_LIMIT"):
            p.run("12:30",dry_run=True,now=self.now)

    def test_readback_requires_correct_photo(self):
        response={"id":"post","message":self.q["caption"],"permalink_url":"https://facebook.com/post",
            "full_picture":"https://example.com/picture","attachments":{"data":[{"target":{"id":"wrong"},"media":{"image":{"src":"https://example.com/picture"}}}]}}
        self.assertFalse(p.readback_matches(response,"post","photo",self.q["caption"]))
        response["attachments"]["data"][0]["target"]["id"]="photo"
        self.assertTrue(p.readback_matches(response,"post","photo",self.q["caption"]))

    def test_external_posts_plus_local_unknown_count_together(self):
        p.write(p.ROOT/"state/posts/unknown.json",{"slot":self.day+"T09:30","status":"publishing"})
        remote={"data":[{"id":str(i),"message":"different", "created_time":self.day+"T04:00:00Z"} for i in range(3)]}
        with patch.object(p,"graph",side_effect=[{"id":p.PAGE_ID},remote]):
            with self.assertRaisesRegex(ValueError,"REMOTE_DAILY_LIMIT"):
                p.remote_dedup(self.q,"fake")

    def test_cas_failure_prevents_post(self):
        with patch.dict("os.environ", {"META_PUBLISH_ENABLED":"true", "META_PAGE_ACCESS_TOKEN":"fake"}):
            with patch.object(p,"remote_dedup"),patch.object(p,"verify_image"),patch.object(p,"persist",side_effect=RuntimeError("CAS rejected")),patch.object(p,"graph") as graph:
                with self.assertRaisesRegex(RuntimeError,"CAS rejected"):
                    p.run("12:30",now=self.now)
                graph.assert_not_called()

    def test_unknown_post_is_called_once_and_never_replayed(self):
        with patch.dict("os.environ", {"META_PUBLISH_ENABLED":"true", "META_PAGE_ACCESS_TOKEN":"fake"}):
            with patch.object(p,"remote_dedup"),patch.object(p,"verify_image"),patch.object(p,"persist"),patch.object(p,"graph",side_effect=TimeoutError) as graph:
                self.assertEqual(p.run("12:30",now=self.now),"unknown")
                self.assertEqual(p.run("12:30",now=self.now),"skipped")
                self.assertEqual(graph.call_count,1)

if __name__ == "__main__":
    unittest.main()
