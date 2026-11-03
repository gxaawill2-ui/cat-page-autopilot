"""No-network tests for reversible two-post pilot and copy-format trial."""
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import content_strategy as s
import auto_replenish as a


class ContentStrategyTests(unittest.TestCase):
    def test_before_effective_date_all_original_slots_remain(self):
        day=dt.date(2026,11,3)
        self.assertEqual([slot for slot in a.SLOTS if s.should_generate(day,slot)],list(a.SLOTS))

    def test_new_empty_days_attempt_only_two_original_language_slots(self):
        for day in (dt.date(2026,11,4),dt.date(2026,11,5),dt.date(2026,11,10)):
            self.assertEqual([slot for slot in a.SLOTS if s.should_generate(day,slot)],
                             ["12:30","19:30"])
        self.assertEqual(a.slot_language(dt.date(2026,11,4),"12:30"),"zh-Hant")
        self.assertEqual(a.slot_language(dt.date(2026,11,4),"19:30"),"en")

    def test_japanese_evening_unchanged(self):
        self.assertTrue(s.should_generate(dt.date(2026,11,6),"19:30"))
        self.assertEqual(a.slot_language(dt.date(2026,11,6),"19:30"),"ja")
        self.assertEqual(s.caption_variant(dt.date(2026,11,6),"19:30","ja"),"standard")

    def test_staggered_variants_in_same_timeslot(self):
        self.assertEqual(s.caption_variant(dt.date(2026,11,4),"12:30","zh-Hant"),"short")
        self.assertEqual(s.caption_variant(dt.date(2026,11,5),"12:30","zh-Hant"),"micro_story")
        self.assertEqual(s.caption_variant(dt.date(2026,11,4),"19:30","en"),"short")
        self.assertEqual(s.caption_variant(dt.date(2026,11,5),"19:30","en"),"micro_story")
        self.assertEqual(s.caption_variant(dt.date(2026,11,18),"12:30","zh-Hant"),"standard")

    def test_caption_quality_gate_does_not_touch_provider(self):
        s.require_caption_format("阿橘端出空碗\n主人以為牠吃完了\n原來是在要求第二份","short")
        s.require_caption_format("貓咪打開帳本\n仔細檢查每一筆\n發現罐罐預算不夠\n嚴肅看著主人\n刪掉了主人的零食\n預算瞬間平衡","micro_story")
        with self.assertRaisesRegex(ValueError,"CAPTION_FORMAT"):
            s.require_caption_format("This is only one line.","short")
        with self.assertRaisesRegex(ValueError,"CAPTION_FORMAT"):
            s.require_caption_format("one\ntwo\nthree","micro_story")
        with self.assertRaisesRegex(ValueError,"CAPTION_SPAM"):
            s.require_caption_format("看貓睡覺\n別忘了按讚追蹤\n牠睡醒了","short")

    def test_target_filter_does_not_mutate_existing_native_records(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,"ROOT",Path(tmp)):
            day=dt.date(2026,11,5)
            before=dt.datetime(2026,11,3,10,0,tzinfo=a.TZ)
            path=Path(tmp)/"state/meta_native"/"2026-11-05-0930.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"status":"scheduled_api_verified","meta_post_id":"preserved"}')
            before_bytes=path.read_bytes()
            slots=list(a.slots_to_fill(before))
            self.assertNotIn((day,"09:30"),slots)
            self.assertIn((day,"12:30"),slots)
            self.assertIn((day,"19:30"),slots)
            self.assertEqual(path.read_bytes(),before_bytes)

    def test_daily_safety_limit_remains_four(self):
        self.assertEqual(a.base.read(a.ROOT/"state/policy.json")["daily_limit"],4)


if __name__=="__main__":
    unittest.main()
