
import unittest

from src.ll_ocl_comics.helpers import remove_between_anchors

class TestRemoveBetweenAnchors(unittest.TestCase):
    def test_remove_between_anchors(self):
        text = "<think> I think I am string. </think> Strong!"
        anchor = "think"
        self.assertEqual(remove_between_anchors(text, anchor), "Strong!")
