import time
import unittest

import relations_unifist


class TestModule(unittest.TestCase):

    maxDiff = None

    def test_module(self):

        self.assertIn("Relations Unifist", relations_unifist.__doc__)

    def test_slugify(self):

        # a name

        self.assertEqual(relations_unifist.slugify("Hello, World!"), "hello-world")
        self.assertEqual(relations_unifist.slugify("  --Many   spaces & symbols__ "), "many-spaces-symbols")
        self.assertEqual(relations_unifist.slugify("42"), "42")

        # titles, the values that make up a record's name

        self.assertEqual(relations_unifist.slugify(["Gaffer", "Fitch"]), "gaffer-fitch")
        self.assertEqual(relations_unifist.slugify(("Unit", 2, None, "")), "unit-2")

        # accents and other scripts fold to plain letters, what can't is dropped

        self.assertEqual(relations_unifist.slugify("Crème Brûlée Ünïcode"), "creme-brulee-unicode")
        self.assertEqual(relations_unifist.slugify("日本語 text"), "text")

        # a length, 32 by default, cut at the last word boundary within it, or at the length if there isn't one

        self.assertEqual(relations_unifist.slugify("the quick brown fox jumps", length=20), "the-quick-brown-fox")
        self.assertEqual(relations_unifist.slugify("one two three four", length=10), "one-two")
        self.assertEqual(relations_unifist.slugify("one two three four", length=7), "one-two")
        self.assertEqual(relations_unifist.slugify("abc", length=10), "abc")
        self.assertEqual(relations_unifist.slugify("Thequickbrownfoxjumpsoverlazydog", length=20), "thequickbrownfoxjump")
        self.assertEqual(relations_unifist.slugify("x" * 100), "x" * 32)
        self.assertEqual(relations_unifist.slugify("x" * 300, length=255), "x" * 255)
        self.assertEqual(relations_unifist.slugify("one-two three", length=8), "one-two")

        # nothing to make one from

        for empty in ["", "!!!", ["", None], [], None]:
            with self.assertRaisesRegex(ValueError, "nothing to make a slug from"):
                relations_unifist.slugify(empty)

        # a length has to fit a string

        for length in [0, 256, -1]:
            with self.assertRaisesRegex(ValueError, "length has to be from 1 to 255"):
                relations_unifist.slugify("abc", length=length)

    def test_microseconds(self):

        before = time.time_ns() // 1000
        now = relations_unifist.microseconds()
        after = time.time_ns() // 1000

        self.assertIsInstance(now, int)
        self.assertTrue(before <= now <= after)


class TestSequence(unittest.TestCase):

    maxDiff = None

    def test_define(self):

        definition = relations_unifist.Sequence.thy().define()
        fields = {field["name"]: field for field in definition["fields"]}

        self.assertEqual(definition["name"], "sequence")
        self.assertEqual(definition["id"], "id")
        self.assertEqual([field["name"] for field in definition["fields"]], ["id", "unum", "source", "model", "current"])
        self.assertEqual([field["kind"] for field in definition["fields"]], ["int", "str", "str", "str", "int"])
        self.assertEqual(definition["unique"], {"unum-source-model": ["unum", "source", "model"]})
        self.assertFalse(fields["unum"]["none"])
        self.assertFalse(fields["source"]["none"])
        self.assertFalse(fields["model"]["none"])
        self.assertEqual(fields["current"]["default"], 0)


class TestSlug(unittest.TestCase):

    maxDiff = None

    def test_define(self):

        definition = relations_unifist.Slug.thy().define()
        fields = {field["name"]: field for field in definition["fields"]}

        self.assertEqual(definition["name"], "slug")
        self.assertEqual(definition["id"], "id")
        self.assertEqual([field["name"] for field in definition["fields"]], ["id", "unum", "source", "model", "current"])
        self.assertEqual([field["kind"] for field in definition["fields"]], ["int", "str", "str", "str", "str"])
        self.assertEqual(definition["unique"], {"unum-source-model-current": ["unum", "source", "model", "current"]})
        for name in ["unum", "source", "model", "current"]:
            self.assertFalse(fields[name]["none"])


class TestJournal(unittest.TestCase):

    maxDiff = None

    def test_define(self):

        definition = relations_unifist.Journal.thy().define()
        fields = {field["name"]: field for field in definition["fields"]}

        self.assertEqual(definition["name"], "journal")
        self.assertEqual(definition["id"], "id")
        self.assertEqual([field["name"] for field in definition["fields"]], ["id", "resource_id", "when", "what"])
        self.assertEqual([field["kind"] for field in definition["fields"]], ["int", "str", "int", "dict"])
        self.assertEqual(definition["unique"], {})
        self.assertEqual(definition["index"], {"resource_id": ["resource_id"]})
        self.assertFalse(fields["resource_id"]["none"])
        self.assertFalse(fields["when"]["none"])
        self.assertFalse(fields["what"]["none"])

        # when is microseconds, filled in on create

        before = time.time_ns() // 1000
        journal = relations_unifist.Journal(resource_id="abc", what={"create": {}})
        self.assertTrue(before <= journal.when <= time.time_ns() // 1000)
