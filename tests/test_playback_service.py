import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workbench"))


class PlaybackServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.audio_root = self.base / "audio"

    def tearDown(self):
        self.temp.cleanup()

    def test_track_key_separates_sources(self):
        from playback_service import track_key

        self.assertEqual(track_key("QQ", 42), "qq:42")
        self.assertEqual(track_key("163", 42), "163:42")
        self.assertNotEqual(track_key("qq", 42), track_key("163", 42))

    def test_bind_upload_persists_and_resolves_after_reload(self):
        from playback_service import PlaybackLibrary

        first = PlaybackLibrary(self.audio_root)
        bound = first.bind_upload("qq", 1001, "demo.MP3", b"ID3-audio")

        self.assertEqual(bound["trackKey"], "qq:1001")
        self.assertEqual(bound["mimeType"], "audio/mpeg")
        self.assertEqual(bound["kind"], "full")
        self.assertNotIn("path", bound)

        second = PlaybackLibrary(self.audio_root)
        resolved = second.resolve("qq", 1001)
        self.assertEqual(resolved["assetId"], bound["assetId"])
        self.assertEqual(second.asset_path(bound["assetId"]).read_bytes(), b"ID3-audio")

    def test_rejects_unsupported_extension(self):
        from playback_service import PlaybackLibrary, PlaybackValidationError

        with self.assertRaisesRegex(PlaybackValidationError, "不支持"):
            PlaybackLibrary(self.audio_root).bind_upload("qq", 1, "song.exe", b"MZ")

    def test_rejects_oversized_body(self):
        import playback_service

        with patch.object(playback_service, "MAX_UPLOAD_BYTES", 3):
            with self.assertRaisesRegex(playback_service.PlaybackValidationError, "200 MiB"):
                playback_service.PlaybackLibrary(self.audio_root).bind_upload(
                    "qq", 1, "song.mp3", b"four"
                )

    def test_rejects_empty_or_unsafe_identity(self):
        from playback_service import PlaybackValidationError, track_key

        for source, track_id in [("", "1"), ("qq", ""), ("../qq", "1"), ("qq", "../1")]:
            with self.subTest(source=source, track_id=track_id):
                with self.assertRaises(PlaybackValidationError):
                    track_key(source, track_id)

    def test_asset_path_never_escapes_root(self):
        from playback_service import PlaybackLibrary

        self.audio_root.mkdir(parents=True)
        outside = self.base / "outside.mp3"
        outside.write_bytes(b"private")
        (self.audio_root / "index.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "tracks": {
                        "qq:7": {
                            "assetId": "escape",
                            "file": "../outside.mp3",
                            "mimeType": "audio/mpeg",
                            "kind": "full",
                            "provider": "upload",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        library = PlaybackLibrary(self.audio_root)
        self.assertIsNone(library.resolve("qq", 7))
        self.assertIsNone(library.asset_path("escape"))

    def test_manifest_entry_resolves_without_mutating_upload_index(self):
        from playback_service import PlaybackLibrary

        licensed = self.audio_root / "licensed" / "sample.wav"
        licensed.parent.mkdir(parents=True)
        licensed.write_bytes(b"RIFF-sample")
        manifest = self.base / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": 1,
                    "tracks": {
                        "163:88": {
                            "file": "licensed/sample.wav",
                            "mimeType": "audio/wav",
                            "kind": "preview",
                            "provider": "licensed-demo",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        library = PlaybackLibrary(self.audio_root, manifest)
        resolved = library.resolve("163", 88)

        self.assertEqual(resolved["trackKey"], "163:88")
        self.assertEqual(resolved["kind"], "preview")
        self.assertEqual(resolved["provider"], "licensed-demo")
        self.assertEqual(library.asset_path(resolved["assetId"]), licensed.resolve())
        self.assertFalse((self.audio_root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
