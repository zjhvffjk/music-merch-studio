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
        with mock.patch.object(ai.requests, "post", return_value=FakeResponse({"output_image": {"data": encoded}})) as post:
            ai.generate(ident, Image.new("RGB", (600, 600)), "inside", "增加蝴蝶")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["model"], "gemini-nano-banana-2.1")
        self.assertEqual(kwargs["json"]["input"][1]["type"], "image")
        self.assertIn("增加蝴蝶", kwargs["json"]["input"][0]["text"])
        self.assertEqual(kwargs["json"]["response_format"]["aspect_ratio"], "1:1")

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
             mock.patch.object(ai.requests, "get", return_value=FakeResponse({"name": "model"})) as get:
            self.assertTrue(ai.test_profile(ident)["ok"])
        self.assertEqual(get.call_args.kwargs["proxies"],
                         {"https": "http://127.0.0.1:10808"})


if __name__ == "__main__":
    unittest.main()
