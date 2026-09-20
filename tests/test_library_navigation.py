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

    def test_toolbar_has_separate_history_back_control(self):
        html = PAGE.read_text(encoding='utf-8')
        self.assertIn('id="btnHistoryBack"', html)
        self.assertIn('function goHistoryBack()', html)
        self.assertIn("$('#btnHistoryBack').onclick=goHistoryBack", html)


if __name__ == '__main__':
    unittest.main()

