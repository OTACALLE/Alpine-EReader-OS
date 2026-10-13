import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from shell.ereader_shell import app


class ShellAppTests(unittest.TestCase):
    def run_app(self, *argv):
        buffer = io.StringIO()
        with mock.patch("sys.argv", ["app", *argv]), redirect_stdout(buffer):
            code = app.main()
        return code, buffer.getvalue()

    def test_lists_books_and_reports_library_screen(self):
        with tempfile.TemporaryDirectory() as tmp:
            books = Path(tmp) / "Books"
            books.mkdir()
            (books / "b.epub").write_text("x")
            (books / "a.pdf").write_text("x")
            code, out = self.run_app("--data-root", tmp)
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1:], ["a.pdf", "b.epub", "screen=library"])

    def test_open_delegates_to_koreader_as_a_separate_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "book.epub"
            book.write_text("x")
            with mock.patch.object(app, "KOReaderLauncher") as launcher:
                launcher.return_value.launch.return_value = 0
                code, _ = self.run_app("--data-root", tmp, "--open", str(book))
            launcher.return_value.launch.assert_called_once_with(book)
        self.assertEqual(code, 0)

    def test_open_missing_book_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_app("--data-root", tmp, "--open", str(Path(tmp) / "nope.epub"))
        self.assertEqual(code, 2)
        self.assertIn("book not found", out)


if __name__ == "__main__":
    unittest.main()
