import contextlib
import http.client
import sys
import threading
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "workbench")]
import server


@contextlib.contextmanager
def running_server():
    httpd = server.Server(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)


def get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read().decode("utf-8")
    conn.close()
    return result


class PlayerMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.links = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.setdefault(attrs["id"], []).append((tag, attrs))
        if tag == "link":
            self.links.append(attrs)
        if tag == "script":
            self.scripts.append(attrs)


class PlayerUiTests(unittest.TestCase):
    def test_page_serves_one_persistent_audio_and_accessible_player_controls(self):
        with running_server() as port:
            status, _, html = get(port, "/")

        parser = PlayerMarkupParser()
        parser.feed(html)
        self.assertEqual(status, 200)
        self.assertEqual(len(parser.ids.get("workbenchAudio", [])), 1)
        self.assertEqual(parser.ids["workbenchAudio"][0][0], "audio")
        self.assertIn("workbenchPlayer", parser.ids)
        for element_id in ("playerPrevious", "playerToggle", "playerNext", "playerMode",
                           "playerProgress", "playerVolume", "playerQueue", "playerExpand"):
            attrs = parser.ids[element_id][0][1]
            self.assertTrue(attrs.get("aria-label"), element_id)

    def test_page_and_server_expose_only_the_player_static_assets(self):
        with running_server() as port:
            _, _, html = get(port, "/")
            css_status, css_headers, css = get(port, "/static/player.css")
            js_status, js_headers, js = get(port, "/static/player.js")
            denied_status, _, _ = get(port, "/static/server.py")

        parser = PlayerMarkupParser()
        parser.feed(html)
        self.assertTrue(any(x.get("href") == "/static/player.css" for x in parser.links))
        self.assertTrue(any(x.get("src") == "/static/player.js" for x in parser.scripts))
        self.assertEqual(css_status, 200)
        self.assertIn("text/css", css_headers["Content-Type"])
        self.assertEqual(js_status, 200)
        self.assertIn("javascript", js_headers["Content-Type"])
        self.assertEqual(denied_status, 404)
        self.assertIn("body.player-visible", css)
        self.assertIn("window.WorkbenchPlayer", js)

    def test_search_renderers_expose_separate_play_controls(self):
        html = (ROOT / "workbench" / "index.html").read_text(encoding="utf-8")
        self.assertGreaterEqual(html.count("data-play-track"), 3)
        self.assertIn("e.stopPropagation();window.WorkbenchPlayer", html)
        self.assertIn("window.openSongMakerTrack", html)

    def test_player_core_persists_queue_without_requesting_autoplay(self):
        js = (ROOT / "workbench" / "player.js").read_text(encoding="utf-8")
        self.assertIn("setQueue", js)
        self.assertIn("playTrack", js)
        self.assertIn("localStorage", js)
        self.assertNotIn("autoplay", js.lower())
        self.assertIn("workbench-player-change", js)


if __name__ == "__main__":
    unittest.main()
