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
    def test_budget_proof_missing_or_unverified_blocks_spend(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(a,"ROOT",Path(tmp)):
            with self.assertRaisesRegex(ValueError,"CLOUDFLARE_FREE_PLAN_NOT_VERIFIED"):
                a.budget_gate(dt.datetime.now(a.TZ))
            a.base.write(Path(tmp)/"state/cloudflare_free.json",{"verified":True})
            with self.assertRaisesRegex(ValueError,"CLOUDFLARE_FREE_PLAN_NOT_VERIFIED"):
                a.budget_gate(dt.datetime.now(a.TZ))

    def test_budget_proof_expiry_blocks_spend(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(a,"ROOT",Path(tmp)):
            b={k:True for k in ("verified","workers_free","no_paid_upgrade","no_gateway_billing","provider_hard_stop")}
            b.update(evidence_record="actual-account-check.json",valid_until="2026-10-01T00:00:00+08:00")
            a.base.write(Path(tmp)/"state/cloudflare_free.json",b)
            with self.assertRaisesRegex(ValueError,"EXPIRED"):
                a.budget_gate(dt.datetime(2026,10,29,tzinfo=a.TZ))

    def test_japanese_test_dates_are_preserved(self):
        for day in (dt.date(2026,11,3),dt.date(2026,11,6)):
            self.assertEqual(a.slot_language(day,"19:30"),"ja")
            self.assertEqual(a.slot_language(day,"09:30"),"en")

    def test_invalid_model_stops_before_generation(self):
        with patch.object(a,"TEXT","unreviewed-paid-model"):
            with self.assertRaisesRegex(ValueError,"MODEL_UNAVAILABLE"):
                a.model_gate()

    def test_real_jpeg_saved_under_deployed_docs_before_qa(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,"ROOT",Path(tmp)), \
             patch.object(a.subprocess,"run") as run:
            run.return_value.returncode=0
            data=b"mock-jpeg-content"
            q=a.commit_queue(dt.date(2026,11,1),"09:30",{"caption":"A brand new cat adventure", "scene":"Original cat scene", "topic":"play"},"en",data)
            self.assertEqual((Path(tmp)/"docs/assets"/(q["image_sha256"]+".jpg")).read_bytes(),data)
            self.assertFalse(q["image_qa"])
            self.assertIn("scene",q)

    def test_unknown_generation_is_not_paid_for_twice(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,"ROOT",Path(tmp)), \
             patch.dict(os.environ,{"CAT_AUTOPILOT_ENABLED":"true","META_PAGE_ACCESS_TOKEN":"fixture","CLOUDFLARE_API_TOKEN":"fixture","CLOUDFLARE_ACCOUNT_ID":"a"*32},clear=True), \
             patch.object(a.native,"remote",return_value=({}, {"posts":[],"scheduled_posts":[]})),patch.object(a.native,"remote_guard"),patch.object(a,"checkpoint"),patch.object(a,"budget_gate"),patch.object(a,"model_gate"), \
             patch.object(a,"slots_to_fill",return_value=[(dt.date(2026,11,1),"09:30")]), \
             patch.object(a,"content",side_effect=AssertionError("No paid replay")):
            a.base.write(Path(tmp)/"state/policy.json",{"daily_limit":4})
            a.base.write(a.generation_file(dt.date(2026,11,1),"09:30"),{"status":"image_armed_unknown"})
            a.run()

    def test_unverified_budget_prevents_all_ai_calls(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,"ROOT",Path(tmp)), \
             patch.dict(os.environ,{"CAT_AUTOPILOT_ENABLED":"true","META_PAGE_ACCESS_TOKEN":"fixture","CLOUDFLARE_API_TOKEN":"fixture","CLOUDFLARE_ACCOUNT_ID":"a"*32},clear=True), \
             patch.object(a.native,"remote"),patch.object(a,"ai",side_effect=AssertionError("No paid calls")):
            with self.assertRaisesRegex(ValueError,"CLOUDFLARE_FREE_PLAN_NOT_VERIFIED"):
                a.run()

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
              "META_PAGE_ACCESS_TOKEN":"expired","CLOUDFLARE_API_TOKEN":"test","CLOUDFLARE_ACCOUNT_ID":"a"*32},clear=True), \
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

    def test_fenced_caption_response_is_preserved_before_parse(self):
        item={"caption":"The cat inspected the empty breakfast bowl again.","scene":"An orange cat peering into a ceramic breakfast bowl in a sunlit kitchen with a skeptical expression and coherent anatomy.","topic":"breakfast"}
        raw="```json\r\n"+json.dumps(item)+"\r\n```"
        saved=[]
        with patch.object(a,"chat",return_value=raw):
            result,_=a.content(dt.date(2026,10,30),"09:30","fixture",raw_sink=saved.append)
        self.assertEqual(saved,[raw])
        self.assertEqual(result,item)

    def test_malformed_caption_keeps_actual_response_for_recovery(self):
        saved=[]
        with patch.object(a,"chat",return_value="No valid JSON returned"):
            with self.assertRaises(json.JSONDecodeError):
                a.content(dt.date(2026,10,30),"09:30","fixture",raw_sink=saved.append)
        self.assertEqual(saved,["No valid JSON returned"])

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

    def test_visual_qa_requires_every_check_and_actual_reason(self):
        keys=("cat_visible","coherent_anatomy","safe_content","no_text_or_signature","no_watermark")
        result={"decision":"PASS","reason":"A coherent cat with clean corners.","checks":dict.fromkeys(keys,True)}
        with patch.object(a,"chat",return_value=json.dumps(result)):
            self.assertTrue(a.qa_image(b"test","cat","key"))
        result["checks"]["no_watermark"]=False
        with patch.object(a,"chat",return_value=json.dumps(result)):
            self.assertFalse(a.qa_image(b"test","cat","key"))
        result["checks"]["no_watermark"]="true"
        with patch.object(a,"chat",return_value=json.dumps(result)):
            self.assertFalse(a.qa_image(b"test","cat","key"))
        with patch.object(a,"chat",return_value="PASS"):
            with self.assertRaises(json.JSONDecodeError): a.qa_image(b"test","cat","key")

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

    def test_missing_pages_build_credential_stops_before_http(self):
        with patch.dict(os.environ,{},clear=True), patch.object(a.urllib.request,"urlopen",side_effect=AssertionError("no HTTP")):
            with self.assertRaisesRegex(ValueError,"credential missing"):
                a.request_pages_build()

    def test_pages_build_rejection_is_not_retried(self):
        from urllib.error import HTTPError
        with patch.dict(os.environ,{"GH_TOKEN":"fixture"}), patch.object(a.urllib.request,"urlopen",side_effect=HTTPError("https://api.github.com",403,"denied",{},None)) as call:
            with self.assertRaisesRegex(ValueError,"PAGES_BUILD_HTTP_403"):
                a.request_pages_build()
            self.assertEqual(call.call_count,1)

    def test_character_profiles_have_stable_distinct_appearances(self):
        chars=a.base.read(a.ROOT/"state/characters.json")["characters"]
        self.assertEqual([c["name"] for c in chars],["阿橘","小雪","小夜","阿斑","咪寶"])
        self.assertEqual(len({c["appearance"] for c in chars}),5)
        self.assertTrue(all(c["personality"] and c["story_style"] for c in chars))

    def test_planner_and_photo_ids_are_not_graph_feed_post_ids(self):
        self.assertFalse(a.genuine_graph_post_id("1135613809012719"))
        self.assertFalse(a.genuine_graph_post_id("122107140813515576"))
        self.assertFalse(a.genuine_graph_post_id("999_122107140849515576"))
        self.assertTrue(a.genuine_graph_post_id("1346385028565797_122107140849515576"))

    def test_direct_gemma_request_disables_thinking_and_keeps_real_metadata(self):
        result={"model":a.TEXT,"usage":{"completion_tokens":42},"choices":[{"finish_reason":"stop","message":{"content":"actual answer"}}]}
        with patch.object(a,"ai",return_value=result) as req:
            self.assertEqual(a.chat([],"fixture",a.TEXT),"actual answer")
        body=req.call_args.args[1]
        self.assertIs(body["chat_template_kwargs"]["enable_thinking"],False)
        self.assertIs(body["stream"],False)
        self.assertEqual(a.LAST_CHAT_METADATA["finish_reason"],"stop")

    def test_empty_answer_preserves_finish_reason_without_claiming_root_cause(self):
        with patch.object(a,"ai",return_value={"choices":[{"finish_reason":"length","message":{"content":None}}]}):
            with self.assertRaisesRegex(ValueError,"No usable"):
                a.chat([],"fixture",a.TEXT)
        self.assertEqual(a.LAST_CHAT_METADATA["finish_reason"],"length")

    def test_existing_queue_cannot_be_overwritten_without_explicit_rejected_image_intent(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,"ROOT",Path(tmp)), patch.object(a.subprocess,"run") as run:
            run.return_value.returncode=0
            day=dt.date(2026,11,1)
            item={"caption":"A unique original kitty adventure","scene":"An original cat in a clean room","topic":"test"}
            q=a.commit_queue(day,"09:30",item,"en",b"first")
            with self.assertRaisesRegex(ValueError,"Never overwrite"):
                a.commit_queue(day,"09:30",item,"en",b"second")
            q["image_qa_method"]="image retry armed unknown"
            qp=Path(tmp)/"queue/meta/2026-11-01/0930.json"
            a.base.write(qp,q)
            second=a.commit_queue(day,"09:30",item,"en",b"second",previous=q)
            self.assertEqual(second["image_attempts"],2)
            self.assertEqual(second["previous_image_attempts"][0]["image_sha256"],q["image_sha256"])
            with self.assertRaisesRegex(ValueError,"Never overwrite"):
                a.commit_queue(day,"09:30",item,"en",b"third",previous=second)

if __name__=="__main__":
    unittest.main()
