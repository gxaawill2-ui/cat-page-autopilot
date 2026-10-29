"""No-network tests for the no-card provider adapter."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch, MagicMock
import cloudflare_ai as cf


class CloudflareSafetyTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32,
                              "CLOUDFLARE_API_TOKEN": "test-only-fixture"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_token_never_connects(self):
        os.environ.pop("CLOUDFLARE_API_TOKEN")
        with patch.object(cf.urllib.request, "build_opener") as opener:
            with self.assertRaisesRegex(ValueError, "credentials missing"):
                cf.request("/chat/completions", {"model": cf.TEXT}, "")
            opener.assert_not_called()

    def test_invalid_account_never_connects(self):
        os.environ["CLOUDFLARE_ACCOUNT_ID"] = "wrong/path"
        with self.assertRaisesRegex(ValueError, "credentials missing"):
            cf.credentials()

    def test_paid_model_and_unknown_endpoint_never_connect(self):
        with patch.object(cf.urllib.request, "build_opener") as opener:
            for endpoint, body in (("/chat/completions", {"model": "@cf/moonshotai/kimi-k2.7-code"}),
                                   ("/billing/upgrade", {})):
                with self.assertRaisesRegex(ValueError, "Unreviewed"):
                    cf.request(endpoint, body, "test-only-fixture")
            opener.assert_not_called()

    def response(self, value):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(value).encode()
        return response

    def test_image_uses_direct_endpoint_four_steps_and_base64(self):
        opener = MagicMock()
        opener.open.return_value = self.response({"success": True, "result": {"image": "YWJj"}})
        with patch.object(cf.urllib.request, "build_opener", return_value=opener):
            result = cf.request("/images/generations", {"model": cf.IMAGE, "prompt": "cat"},
                                "test-only-fixture")
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, cf.ORIGIN + "a" * 32 + "/ai/run/" + cf.IMAGE)
        self.assertEqual(json.loads(req.data), {"prompt": "cat", "steps": 4})
        self.assertEqual(result, {"data": [{"b64_json": "YWJj"}]})

    def test_chat_returns_compatible_content(self):
        opener = MagicMock()
        opener.open.return_value = self.response({"choices": [{"message": {"content": "PASS"}}]})
        with patch.object(cf.urllib.request, "build_opener", return_value=opener):
            result = cf.request("/chat/completions", {"model": cf.VISION}, "test-only-fixture")
        self.assertEqual(result["choices"][0]["message"]["content"], "PASS")

    def test_quota_failure_is_single_call_and_redacts_body(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://api.cloudflare.com", 429,
                                      "secret raw error", {}, io.BytesIO(b"private-body"))
        with patch.object(cf.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(RuntimeError, "^CLOUDFLARE_HTTP_429$"):
                cf.request("/chat/completions", {"model": cf.TEXT}, "test-only-fixture")
        self.assertEqual(opener.open.call_count, 1)

    def test_redirect_never_forwards_token(self):
        with self.assertRaisesRegex(RuntimeError, "credential not forwarded"):
            cf.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example")

    def test_missing_image_does_not_fetch_a_provider_url(self):
        opener = MagicMock()
        opener.open.return_value = self.response({"success": True, "result": {"url": "https://other.example"}})
        with patch.object(cf.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "base64 image"):
                cf.request("/images/generations", {"model": cf.IMAGE, "prompt": "cat"}, "test-only-fixture")
        self.assertEqual(opener.open.call_count, 1)


if __name__ == "__main__":
    unittest.main()
