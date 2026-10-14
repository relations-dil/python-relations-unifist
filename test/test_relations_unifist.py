import unittest

import relations_unifist


class TestModule(unittest.TestCase):

    maxDiff = None

    def test_module(self):

        self.assertIn("Relations Unifist", relations_unifist.__doc__)
