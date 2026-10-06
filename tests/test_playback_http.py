import contextlib
import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "workbench")]

from playback_service import PlaybackLibrary
import server


@contextlib.contextmanager
def running_server(library):
    previous = getattr(server, "PLAYBACK", None)
    server.PLAYBACK = library
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
        if previous is None:
            delattr(server, "PLAYBACK")
        else:
            server.PLAYBACK = previous


def request(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    payload = response.read()
    result = (response.status, dict(response.getheaders()), payload)
    conn.close()
    return result


class PlaybackHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.library = PlaybackLibrary(Path(self.temp.name) / "audio")

    def tearDown(self):
        self.temp.cleanup()

    def test_playback_lookup_returns_bound_and_unbound_state(self):
        bound = self.library.bind_upload("qq", 7, "song.mp3", b"ID3-audio")
        with running_server(self.library) as port:
            status, _, body = request(port, "GET", "/api/playback?source=qq&id=7")
            available = json.loads(body)
            status2, _, body2 = request(port, "GET", "/api/playback?source=163&id=7")
            missing = json.loads(body2)

        self.assertEqual(status, 200)
        self.assertTrue(available["playable"])
        self.assertEqual(available["asset"]["trackKey"], "qq:7")
        self.assertEqual(available["asset"]["url"], f"/media/audio/{bound['assetId']}")
        self.assertEqual(status2, 200)
        self.assertFalse(missing["playable"])
        self.assertIn("没有可播放音源", missing["reason"])

    def test_audio_upload_binds_track_and_rejects_invalid_type(self):
        with running_server(self.library) as port:
            query = urlencode({"source": "163", "id": "88", "name": "mine.wav"})
            status, _, body = request(
                port,
                "POST",
                "/api/audio/upload?" + query,
                b"RIFF-audio",
                {"Content-Type": "application/octet-stream", "Content-Length": "10"},
            )
            uploaded = json.loads(body)
            bad_query = urlencode({"source": "163", "id": "89", "name": "bad.exe"})
            bad_status, _, bad_body = request(
                port,
                "POST",
                "/api/audio/upload?" + bad_query,
                b"MZ",
                {"Content-Type": "application/octet-stream", "Content-Length": "2"},
            )

        self.assertEqual(status, 200)
        self.assertTrue(uploaded["playable"])
        self.assertEqual(self.library.state("163", 88), "playable")
        self.assertEqual(bad_status, 400)
        self.assertIn("不支持", json.loads(bad_body)["error"])

    def test_audio_route_supports_full_and_byte_range_requests(self):
        bound = self.library.bind_upload("qq", 9, "ten.mp3", b"0123456789")
        path = f"/media/audio/{bound['assetId']}"
        with running_server(self.library) as port:
            full = request(port, "GET", path)
            first = request(port, "GET", path, headers={"Range": "bytes=0-3"})
            open_end = request(port, "GET", path, headers={"Range": "bytes=4-"})
            suffix = request(port, "GET", path, headers={"Range": "bytes=-4"})
            beyond = request(port, "GET", path, headers={"Range": "bytes=99-"})
            malformed = request(port, "GET", path, headers={"Range": "bytes=abc"})

        self.assertEqual((full[0], full[2]), (200, b"0123456789"))
        self.assertEqual((first[0], first[2]), (206, b"0123"))
        self.assertEqual(first[1]["Content-Range"], "bytes 0-3/10")
        self.assertEqual((open_end[0], open_end[2]), (206, b"456789"))
        self.assertEqual((suffix[0], suffix[2]), (206, b"6789"))
        self.assertEqual(beyond[0], 416)
        self.assertEqual(beyond[1]["Content-Range"], "bytes */10")
        self.assertEqual(malformed[0], 416)

    def test_song_search_includes_stable_playback_fields(self):
        qq_song = {
            "songid": 321,
            "songname": "Test Song",
            "singer": [{"name": "Singer"}],
            "albumname": "Album",
            "interval": 123,
            "albummid": "album-mid",
        }
        self.library.bind_upload("qq", 321, "test.mp3", b"ID3-test")
        with patch.object(server, "search_song_q", return_value=[qq_song]), \
             running_server(self.library) as port:
            status, _, body = request(port, "GET", "/api/song?name=Test&source=qq")

        song = json.loads(body)["songs"][0]
        self.assertEqual(status, 200)
        self.assertEqual(song["source"], "qq")
        self.assertEqual(song["trackKey"], "qq:321")
        self.assertEqual(song["playbackState"], "playable")

    def test_artist_search_includes_source_and_playback_fields(self):
        artist = {"id": "singer-mid", "name": "Singer", "albumSize": 1}
        pool = [{
            "id": 55,
            "name": "Hot Song",
            "artists": "Singer",
            "album": "Album",
            "dur_ms": 1000,
            "pic": "album-mid",
        }]
        with patch.object(server, "pick_source", return_value=("qq", artist, pool, [])), \
             running_server(self.library) as port:
            status, _, body = request(port, "GET", "/api/artist?name=Singer&source=qq")

        song = json.loads(body)["songs"][0]
        self.assertEqual(status, 200)
        self.assertEqual(song["source"], "qq")
        self.assertEqual(song["trackKey"], "qq:55")
        self.assertEqual(song["playbackState"], "unavailable")


if __name__ == "__main__":
    unittest.main()
