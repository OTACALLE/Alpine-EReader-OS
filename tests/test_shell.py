import unittest

from shell.ereader_shell.state import Screen, ShellState


class ShellTests(unittest.TestCase):
    def test_navigation_is_a_single_stack(self):
        state = ShellState()
        state.open(Screen.SETTINGS)
        state.open(Screen.NETWORK)
        self.assertEqual(state.back(), Screen.SETTINGS)
        self.assertEqual(state.back(), Screen.LIBRARY)

    def test_opening_book_enters_reader(self):
        state = ShellState()
        state.open_book("/var/lib/ereader/Books/demo.epub")
        self.assertEqual(state.screen, Screen.READER)
        self.assertEqual(state.selected_book, "/var/lib/ereader/Books/demo.epub")
