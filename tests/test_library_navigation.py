import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / 'workbench' / 'index.html'


class LibraryNavigationTests(unittest.TestCase):
    def test_library_work_can_reopen_its_delivery_page(self):
        html = PAGE.read_text(encoding='utf-8')
        self.assertIn('function libOpenWork(id, restoredJob)', html)
        self.assertIn('打开制作结果', html)
        self.assertIn("setAppBack('← 返回作品库'", html)
        self.assertIn("pushAppRoute('library-output'", html)



if __name__ == '__main__':
    unittest.main()

