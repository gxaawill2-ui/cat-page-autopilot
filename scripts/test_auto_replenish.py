"""Safety tests for unattended AI replenishment; no network, no Facebook writes."""
import base64
import datetime as dt
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import auto_replenish as a

class ReplenishSafetyTest(unittest.TestCase):
    def test_preview_calls_no_external_provider(self):
        with patch.object(a,"ai",side_effect=AssertionError("AI must not run")), \
             patch.object(a.native,"remote",side_effect=AssertionError("Meta must not run")):
            a.run(dry=True)

    def test_disabled_never_calls_provider(self):
        with patch.dict(os.environ,{"CAT_AUTOPILOT_ENABLED":"false"},clear=True), \
             patch.object(a,"ai",side_effect=AssertionError("AI must not run")), \
             patch.object(a.native,"remote",side_effect=AssertionError("Meta must not run")):
            with self.assertRaisesRegex(ValueError,"disabled"):
                a.run()

    def test_no_credentials_never_sends(self):
        with patch.dict(os.environ,{"CAT_AUTOPILOT_ENABLED":"true"},clear=True), \
             patch.object(a.native,"remote",side_effect=AssertionError("Meta must not run")):
            with self.assertRaisesRegex(ValueError,"Credentials missing"):
                a.run()

    def test_expired_meta_token_stops_before_paid_ai(self):
        with patch.dict(os.environ,{"CAT_AUTOPILOT_ENABLED":"true",
              "META_PAGE_ACCESS_TOKEN":"expired","AI_GATEWAY_API_KEY":"test"},clear=True), \
             patch.object(a.native,"remote",side_effect=ValueError("HTTP401 expired")), \
             patch.object(a,"ai",side_effect=AssertionError("AI must not run")):
            with self.assertRaisesRegex(ValueError,"HTTP401 expired"):
                a.run()

    def test_language_is_original_slot_language(self):
        txt=json.dumps({"caption":"The sleepy cat found a cozy spot by the window.",
                        "scene":"A charming ginger tabby resting beside the window in soft warm morning sunlight, painterly cozy room and subtle textures.",
                        "topic":"cat naps"})
        with patch.object(a,"chat",return_value=txt):
            result,language=a.content(dt.date(2026,11,1),"09:30","key")
            self.assertEqual(language,"en")
            self.assertEqual(result["topic"],"cat naps")
            result,language=a.content(dt.date(2026,11,1),"16:30","key")
            self.assertEqual(language,"zh-Hant")

    def test_bad_image_rejected(self):
        image=Image.new("RGB",(64,64),color="white")
        buf=io.BytesIO();image.save(buf,format="PNG")
        with patch.object(a,"ai",return_value={"data":[{"b64_json":base64.b64encode(buf.getvalue()).decode()}]}):
            with self.assertRaisesRegex(ValueError,"too small"):
                a.make_image("cat","key")

    def test_missing_image_payload_stops(self):
        with patch.object(a,"ai",return_value={"data":[{"url":"https://unknown.example/unsafe.png"}]}):
            with self.assertRaisesRegex(ValueError,"base64 image"):
                a.make_image("cat","key")

    def test_visual_qa_must_say_exact_pass(self):
        with patch.object(a,"chat",return_value="FAIL"):
            self.assertFalse(a.qa_image(b"test","cat","key"))
        with patch.object(a,"chat",return_value="PASS"):
            self.assertTrue(a.qa_image(b"test","cat","key"))

    def test_existing_native_slot_never_requeued(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_root=a.ROOT
            try:
                a.ROOT=Path(tmp)
                now=dt.datetime(2026,11,1,8,0,tzinfo=a.TZ)
                all_slots=list(a.slots_to_fill(now))
                self.assertIn((dt.date(2026,11,1),"09:30"),all_slots)
                record=Path(tmp)/"state/meta_native"/"2026-11-01-0930.json"
                record.parent.mkdir(parents=True)
                record.write_text('{"status":"schedule_armed_unknown"}')
                self.assertNotIn((dt.date(2026,11,1),"09:30"),list(a.slots_to_fill(now)))
            finally:
                a.ROOT=old_root

if __name__=="__main__":
    unittest.main()
