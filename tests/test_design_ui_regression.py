import unittest
from pathlib import Path

class DesignUiRegressionTests(unittest.TestCase):
    def test_build_button_is_not_permanently_disabled_and_missing_title_controls_are_safe(self):
        html = (Path(__file__).resolve().parents[1] / 'workbench' / 'design.html').read_text(encoding='utf-8')
        self.assertIn('function syncBuildEnabled()', html)
        self.assertIn("titleMode:titleMode?titleMode.value:'cover-follow'", html)
        self.assertIn('const titleAssetFile=$(\'#titleAssetFile\');', html)
        self.assertIn('if(titleAssetFile){', html)
        self.assertIn("const el=$('#'+id); if(!el)return;", html)
        self.assertIn("syncRail();\n  syncBuildEnabled();\n\n  const fu", html)
        self.assertIn('<button id="btnBuild" class="btn">生成三件套</button>', html)

if __name__ == '__main__':
    unittest.main()
