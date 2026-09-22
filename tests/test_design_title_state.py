import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "workbench"), str(ROOT / "tools")]


class DesignTitleStateTests(unittest.TestCase):
    def test_title_state_has_four_unavailable_slots_for_artistic_mode(self):
        from design_service import _title_state
        state = _title_state({"titleMode": "artistic"}, {"style": "retro", "mood": "dreamy"}, "如果呢", "郑润泽")
        self.assertEqual("unavailable", state["providerStatus"])
        self.assertEqual(4, len(state["slots"]))


if __name__ == "__main__":
    unittest.main()
