import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'workbench')]
import server


class SelectedSongTests(unittest.TestCase):
    def test_two_qq_tracks_in_same_album_keep_their_own_identity(self):
        seen = []
        def render(job, song, rank, opt):
            seen.append(song.copy())
            return {'name': song['name']}, None
        with patch.object(server, 'render_song', side_effect=render), \
             patch.object(server, 'finish'), patch.object(server, 'log'), \
             patch.object(server, 'search_song_q', side_effect=AssertionError('Must not re-search')):
            for sid, name in [(101, 'Track A'), (102, 'Track B')]:
                server.run_song({'items': []}, {'song': name, 'songId': sid,
                    'songSource': 'qq', 'albummid': 'shared-album',
                    'selectedSong': {'name': name, 'artist': 'Artist', 'dur': '04:12'}})
        self.assertEqual([s['id'] for s in seen], [101, 102])
        self.assertEqual([s['name'] for s in seen], ['Track A', 'Track B'])
        self.assertEqual(seen[0]['dur_ms'], 252000)

    def test_netease_selection_uses_id_not_search_order(self):
        exact = {'id': 102, 'name': 'Track B', 'artists': [{'name':'Artist'}],
                 'album': {'name':'Album', 'picUrl':'https://p1.music.126.net/test.jpg'}}
        with patch.object(server, 'get_json', return_value={'songs':[exact]}), \
             patch.object(server, 'render_song', return_value=({'name':'Track B'},None)) as render, \
             patch.object(server, 'finish'), patch.object(server, 'log'), \
             patch.object(server, 'search', side_effect=AssertionError('Must not re-search')):
            server.run_song({'items':[]}, {'song':'query','songId':102,'songSource':'163',
                                         'selectedSong':{'name':'Track B'}})
        self.assertEqual(render.call_args.args[1]['id'],102)
