"""AI profile secrecy and image-provider request contracts (no paid calls)."""
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workbench"))
import design_ai as ai


class FakeResponse:
    ok = True
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


def sample_png():
    buffer = io.BytesIO()
    Image.new("RGB", (512, 512), "pink").save(buffer, "PNG")
    return buffer.getvalue()


@unittest.skipUnless(sys.platform == "win32", "DPAPI is Windows-only")
class DesignAiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        file_patch = mock.patch.object(ai, "PROFILE_FILE", root / "profiles.json")
        upload_patch = mock.patch.object(ai, "UPLOAD_DIR", root / "uploads")
        file_patch.start(); upload_patch.start()
        self.addCleanup(file_patch.stop); self.addCleanup(upload_patch.stop)

    def create(self, provider="openai"):
        return ai.save_profile({"name": "图片模型", "provider": provider,
                                "model": ai.PROVIDERS[provider]["model"],
                                "apiKey": "test-private-key"})["profile"]["id"]

    def test_profile_key_is_encrypted_and_never_listed(self):
        ident = self.create()
        self.assertEqual(ai._profile(ident)[1], "test-private-key")
        self.assertNotIn("test-private-key", ai.PROFILE_FILE.read_text(encoding="utf-8"))
        self.assertNotIn("test-private-key", str(ai.list_profiles()))
        self.assertTrue(ai.list_profiles()["profiles"][0]["hasKey"])
        ai.save_profile({"id": ident, "name": "更新名称", "provider": "openai",
                         "model": "gpt-image-2.5-sunburst"})
        self.assertEqual(ai._profile(ident)[1], "test-private-key")

    def test_switching_provider_requires_its_own_key(self):
        ident = self.create("gemini")
        with self.assertRaisesRegex(ai.ModelError, "新 API Key"):
            ai.save_profile({"id": ident, "name": "换服务商", "provider": "openai",
                             "model": "gpt-image-2.5-sunburst"})
        self.assertEqual(ai._profile(ident)[0]["provider"], "gemini")

    def test_openai_receives_reference_and_natural_language(self):
        ident = self.create()
        encoded = base64.b64encode(sample_png()).decode("ascii")
        with mock.patch.object(ai.requests, "post", return_value=FakeResponse({"data": [{"b64_json": encoded}]})) as post:
            result = ai.generate(ident, Image.new("RGB", (600, 600)), "disc",
                                 "改成粉色水晶", "万花筒", "白鹿",
                                 [{"title": "真实曲目", "duration": "02:58"}])
        self.assertTrue((ai.UPLOAD_DIR / (result["upload"] + ".png")).is_file())
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["data"]["model"], "gpt-image-2.5-sunburst")
        self.assertIn("改成粉色水晶", kwargs["data"]["prompt"])
        self.assertIn("真实曲目  02:58", kwargs["data"]["prompt"])
        self.assertEqual(kwargs["files"][0][0], "image[]")
        self.assertNotIn("test-private-key", str(result))

    def test_gemini_receives_reference_image_and_prompt(self):
        ident = self.create("gemini")
        encoded = base64.b64encode(sample_png()).decode("ascii")
        body = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": encoded}}]}}]}
        with mock.patch.object(ai.requests, "post", return_value=FakeResponse(body)) as post:
            ai.generate(ident, Image.new("RGB", (600, 600)), "inside", "增加蝴蝶")
        kwargs = post.call_args.kwargs
        self.assertIn("/v1beta/models/gemini-nano-banana-2.1:generateContent", post.call_args.args[0])
        self.assertIn("inline_data", kwargs["json"]["contents"][0]["parts"][1])
        self.assertIn("增加蝴蝶", kwargs["json"]["contents"][0]["parts"][0]["text"])
        self.assertEqual(kwargs["json"]["generationConfig"]["imageConfig"]["aspectRatio"], "1:1")

    def test_ark_receives_cover_and_previous_component_as_reference_images(self):
        ident = self.create("volcengine")
        encoded = base64.b64encode(sample_png()).decode("ascii")
        with mock.patch.object(ai.requests, "post", return_value=FakeResponse({"data": [{"b64_json": encoded}]})) as post:
            result = ai.generate(ident, Image.new("RGB", (600, 600)), "disc", "增加蝴蝶",
                                 source=Image.new("RGB", (512, 512)))
        self.assertEqual(post.call_args.args[0], "https://ark.cn-beijing.volces.com/api/v3/images/generations")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "doubao-seedream-5-0-flash-260915")
        self.assertEqual(len(body["image"]), 2)
        self.assertTrue(body["image"][0].startswith("data:image/png;base64,"))
        self.assertEqual(body["size"], "2K")
        self.assertTrue((ai.UPLOAD_DIR / (result["upload"] + ".png")).is_file())

    def test_custom_endpoint_and_protocol_survive_editing(self):
        profile = ai.save_profile({"provider": "custom", "protocol": "openai",
            "baseUrl": "https://images.example.com/v1/", "model": "vendor/image-edit",
            "apiKey": "test-private-key"})["profile"]
        self.assertEqual(profile["baseUrl"], "https://images.example.com/v1")
        ai.save_profile({"id": profile["id"], "provider": "custom", "protocol": "openai",
            "baseUrl": profile["baseUrl"], "model": "vendor/image-edit-v2"})
        self.assertEqual(ai._profile(profile["id"])[1], "test-private-key")
        with self.assertRaisesRegex(ai.ModelError, "新 API Key"):
            ai.save_profile({"id": profile["id"], "provider": "custom", "protocol": "openai",
                "baseUrl": "https://different.example.com/v1", "model": "image-edit"})

    def test_rejects_endpoint_with_embedded_credentials(self):
        with self.assertRaises(ai.ModelError):
            ai.save_profile({"provider": "custom", "protocol": "openai",
                "baseUrl": "https://name:secret@example.com/v1", "apiKey": "test-private-key", "model": "image"})

    def test_model_list_filters_text_models_without_claiming_access(self):
        ident = self.create("volcengine")
        with mock.patch.object(ai.requests, "get", return_value=FakeResponse({"data": [
            {"id": "doubao-seedream-5-0-flash-260915"}, {"id": "text-chat"}]})):
            result = ai.list_models(ident)
        self.assertEqual(result["models"], ["doubao-seedream-5-0-flash-260915"])
        self.assertIn("开通权限", result["message"])

    def test_upstream_error_does_not_echo_provider_credentials(self):
        response = FakeResponse({"error": {"message": "Invalid key ark-example-private-12345678"}})
        response.ok = False
        response.status_code = 401
        with self.assertRaises(ai.ModelError) as caught:
            ai._json_response(response)
        self.assertNotIn("ark-example-private", str(caught.exception))

    def test_quota_error_is_clear(self):
        response = FakeResponse({"error": {"message": "You exceeded your current quota"}})
        response.ok = False
        response.status_code = 429
        with self.assertRaisesRegex(ai.ModelError, "配额与结算设置"):
            ai._json_response(response)

    def test_zero_free_tier_quota_is_not_described_as_temporary(self):
        response = FakeResponse({"error": {"message": "Rate limit exceeded (limit: 0 input tokens per minute on Free Tier)"}})
        response.ok = False
        response.status_code = 429
        with self.assertRaisesRegex(ai.ModelError, "免费生成额度为 0"):
            ai._json_response(response)

    def test_component_shapes_and_fixed_back_details(self):
        ident = self.create()
        encoded = base64.b64encode(sample_png()).decode("ascii")
        with mock.patch.object(ai.requests, "post", return_value=FakeResponse({"data": [{"b64_json": encoded}]})) as post:
            ai.generate(ident, Image.new("RGB", (600, 600)), "back", "",
                        "万花筒", "白鹿", [{"title": "万花筒梦境", "duration": "02:58"}],
                        "唱片公司", None, barcode="6971234567891",
                        copyright_text="固定版权声明", release_year="2026")
        self.assertEqual(post.call_args.kwargs["data"]["size"], "1536x1024")
        prompt = post.call_args.kwargs["data"]["prompt"]
        for required in ("万花筒梦境", "6971234567891", "固定版权声明", "2026"):
            self.assertIn(required, prompt)
        self.assertEqual(ai.ASPECTS["right-spine"], ("1024x1536", "9:16"))

    def test_delete_profile_removes_default(self):
        ident = self.create()
        self.assertEqual(ai.list_profiles()["default"], ident)
        ai.delete_profile(ident)
        self.assertEqual(ai.list_profiles()["default"], "")

    def test_connection_uses_current_windows_proxy(self):
        ident = self.create("gemini")
        with mock.patch.object(ai.urllib.request, "getproxies_registry",
                               return_value={"https": "http://127.0.0.1:10808"}), \
             mock.patch.object(ai.requests, "get", return_value=FakeResponse({"name": "model", "supportedGenerationMethods": ["generateContent"]})) as get:
            self.assertTrue(ai.test_profile(ident)["ok"])
        self.assertEqual(get.call_args.kwargs["proxies"],
                         {"https": "http://127.0.0.1:10808"})

    def test_text_model_is_not_reported_as_image_ready(self):
        ident = self.create("gemini")
        ai.save_profile({"id": ident, "provider": "gemini", "model": "gemini-3-flash"})
        with mock.patch.object(ai.requests, "get", return_value=FakeResponse(
                {"supportedGenerationMethods": ["generateContent"]})):
            with self.assertRaisesRegex(ai.ModelError, "文本模型"):
                ai.test_profile(ident)


if __name__ == "__main__":
    unittest.main()
