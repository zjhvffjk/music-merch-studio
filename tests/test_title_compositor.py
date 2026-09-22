import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/"tools")]
import spec_minicd as SP
from title_compositor import intersects, resolve_title_placement
class TitleCompositorTests(unittest.TestCase):
 def test_disc_asset_does_not_intersect_hole(self):
  p=resolve_title_placement("disc",SP,{})
  self.assertFalse(intersects(p.bounds_mm,SP.disc_hole_bounds_mm()))
 def test_back_asset_avoids_all_production_rectangles(self):
  p=resolve_title_placement("back",SP,{})
  self.assertFalse(any(intersects(p.bounds_mm,r) for r in SP.back_protected_rects_mm()))
if __name__=="__main__": unittest.main()
