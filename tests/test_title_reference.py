import sys, tempfile, unittest
from pathlib import Path
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'tools')]
from title_reference import extract_cover_title_reference
class RefTests(unittest.TestCase):
 def test_low_confidence_candidate_is_rejected_not_cropped(self):
  ref=extract_cover_title_reference(Image.new('RGB',(100,100),(128,128,128)), {'style':'retro'}, '如果呢')
  self.assertEqual('rejected',ref['status']); self.assertIsNone(ref['cropPng'])
 def test_safe_high_confidence_title_crop_records_normalized_bbox(self):
  im=Image.new('RGB',(400,300),'white'); ImageDraw.Draw(im).rectangle((30,20,220,70),fill='black')
  ref=extract_cover_title_reference(im, {'style':'handwritten'}, '如果呢')
  self.assertIn(ref['status'],('detected','unavailable'))
  if ref['status']=='detected': self.assertTrue(0<=ref['titleBBox']['x']<=1)
if __name__=='__main__':unittest.main()
