import sys
import time
import unittest

import flask
import flask_restx

import relations
import relations.unittest
import relations_restx

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
        for name in ["unum", "source", "model"]:
            self.assertEqual(fields[name]["length"], 64)
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
        for name in ["unum", "source", "model"]:
            self.assertEqual(fields[name]["length"], 64)
        self.assertNotIn("length", fields["current"])


class TestJournal(unittest.TestCase):

    maxDiff = None

    def test_define(self):

        definition = relations_unifist.Journal.thy().define()
        fields = {field["name"]: field for field in definition["fields"]}

        self.assertEqual(definition["name"], "journal")
        self.assertEqual(definition["id"], "id")
        self.assertEqual([field["name"] for field in definition["fields"]], ["id", "resource_id", "when", "what"])
        self.assertEqual([field["kind"] for field in definition["fields"]], ["str", "str", "int", "dict"])
        self.assertEqual(definition["unique"], {})
        self.assertEqual(definition["index"], {"resource_id": ["resource_id"]})
        self.assertFalse(fields["resource_id"]["none"])
        self.assertFalse(fields["when"]["none"])
        self.assertFalse(fields["what"]["none"])

        # when is microseconds, filled in on create

        before = time.time_ns() // 1000
        journal = relations_unifist.Journal(id="1:abc:thing.local:home:home", resource_id="abc", what={"create": {}})
        self.assertTrue(before <= journal.when <= time.time_ns() // 1000)


class TestUnifistBase(unittest.TestCase):

    maxDiff = None

    def tearDown(self):

        relations_unifist.UnifistBase.SOURCE = "unifist"
        relations_unifist.UnifistModel.UNUM = None

    def test_source(self):

        # The tables are kept in a source named unifist unless it's changed, once, on the lib

        self.assertEqual(relations_unifist.Sequence.SOURCE, "unifist")
        self.assertEqual(relations_unifist.Slug.SOURCE, "unifist")
        self.assertEqual(relations_unifist.Journal.SOURCE, "unifist")

        relations_unifist.UnifistBase.SOURCE = "ledger-unifist"

        self.assertEqual(relations_unifist.Sequence.SOURCE, "ledger-unifist")
        self.assertEqual(relations_unifist.Slug.SOURCE, "ledger-unifist")
        self.assertEqual(relations_unifist.Journal.SOURCE, "ledger-unifist")

        # The app makes a source with that name, separate from the one its models are in, and that's where
        # the ids and the journal go

        unifist = relations.unittest.MockSource("ledger-unifist")
        local = relations.unittest.MockSource("local")

        relations_unifist.UnifistModel.UNUM = "home"

        item = Item(name="a").create()

        self.assertEqual(item.id, "1:item.local:home")
        self.assertEqual(list(local.data["item"]), ["1:item.local:home"])
        self.assertEqual([row["current"] for row in unifist.data["sequence"].values()], [1])
        self.assertEqual([row["resource_id"] for row in unifist.data["journal"].values()], ["1:item.local:home"])


class Base(relations_unifist.UnifistModel):

    SOURCE = "local"


class Thing(Base):

    id = str
    version = int, 1
    unum = str


class Other(Base):

    id = str
    version = int, 1
    unum = str


class Third(Base):

    id = str
    version = int, 1
    unum = str


class Page(Base):

    id = str
    version = int, 1
    unum = str
    title = str

    SLUG = "title"


class Person(Base):

    id = str
    version = int, 1
    unum = str
    first = str
    last = str

    SLUG = ["first", "last"]


class Item(Base):

    id = str
    version = int, 1
    unum = str
    name = str


class IntId(relations_unifist.UnifistModel):

    id = int
    version = int, 1
    unum = str


class NoVersion(relations_unifist.UnifistModel):

    id = str
    title = str


class NoUnum(relations_unifist.UnifistModel):

    id = str
    version = int, 1
    title = str


class IntUnum(relations_unifist.UnifistModel):

    id = str
    version = int, 1
    unum = int


class BadSlug(relations_unifist.UnifistModel):

    id = str
    version = int, 1
    unum = str
    title = str

    SLUG = "nope"


class BadSlugs(relations_unifist.UnifistModel):

    id = str
    version = int, 1
    unum = str
    title = str

    SLUG = ["title", "nope"]


class TestUnifistModel(unittest.TestCase):

    maxDiff = None

    def setUp(self):

        self.unifist = relations.unittest.MockSource("unifist")
        self.local = relations.unittest.MockSource("local")

        # The unum is set once, on the base, when an app starts, and every model sees it

        relations_unifist.UnifistModel.UNUM = "home"

    def tearDown(self):

        relations_unifist.UnifistModel.UNUM = None
        relations_unifist.UnifistModel.JOURNAL = True

    def journal(self):

        return list(self.unifist.data["journal"].values())

    def counted(self, action):

        calls = []
        real = getattr(self.local, action)

        def counting(model, *args, **kwargs):
            calls.append(model)
            return real(model, *args, **kwargs)

        setattr(self.local, action, counting)

        return calls

    def test_define(self):

        # The unifist source is unifist by default, and set on the app's base and inherited, a different source than the app's

        self.assertEqual(relations_unifist.UnifistModel.UNIFIST, "unifist")
        self.assertEqual(Thing.UNIFIST, "unifist")
        self.assertNotEqual(Thing.UNIFIST, Thing.SOURCE)

        # The unum is set on the base and inherited, the slug is set on the model, and it's none by default

        self.assertEqual(Thing.UNUM, "home")
        self.assertEqual(Page.SLUG, "title")
        self.assertIsNone(Thing.SLUG)
        self.assertIsNone(relations_unifist.UnifistModel.SLUG)

    def test___init__(self):

        # Fine with an id string, a version int, a unum string, and a SLUG that is a field or a list of them

        self.assertEqual(Thing().version, 1)
        self.assertEqual(Page(title="Hello").title, "Hello")
        self.assertEqual(Person(first="Gaffer", last="Fitch").last, "Fitch")

        # The id has to be a str and there has to be a version and a unum, a str

        with self.assertRaisesRegex(relations.ModelError, "int_id: id has to be a str field"):
            IntId()

        with self.assertRaisesRegex(relations.ModelError, "no_version: version has to be an int field"):
            NoVersion()

        with self.assertRaisesRegex(relations.ModelError, "no_unum: unum has to be a str field"):
            NoUnum()

        with self.assertRaisesRegex(relations.ModelError, "int_unum: unum has to be a str field"):
            IntUnum()

        # A SLUG has to name fields the model has

        with self.assertRaisesRegex(relations.ModelError, "bad_slug: SLUG field nope not found"):
            BadSlug()

        with self.assertRaisesRegex(relations.ModelError, "bad_slugs: SLUG field nope not found"):
            BadSlugs()

    def test_generate_id(self):

        # With no SLUG it's seq.model.source.unum, the sequence kept in the unifist source

        self.assertEqual(Thing().generate_id(), "1:thing.local:home")
        self.assertEqual(self.unifist.data["sequence"], {1: {"id": 1, "unum": "home", "source": "local", "model": "thing", "current": 1}})
        self.assertEqual(Thing().generate_id(), "2:thing.local:home")
        self.assertEqual(self.unifist.data["sequence"][1]["current"], 2)

        # Another model is another counter

        self.assertEqual(Other().generate_id(), "1:other.local:home")
        self.assertEqual(len(self.unifist.data["sequence"]), 2)

        # If someone else took one between reading and updating, it reads again

        update = self.unifist.update
        taken = []

        def racing(model):
            if not taken:
                taken.append(True)
                self.unifist.data["sequence"][1]["current"] += 1
            return update(model)

        self.unifist.update = racing

        self.assertEqual(Thing().generate_id(), "4:thing.local:home")
        self.assertEqual(self.unifist.data["sequence"][1]["current"], 4)

        # Or if someone else inserted the counter first

        self.unifist.update = update
        create = self.unifist.create

        def inserting(model):
            self.unifist.create = create
            relations_unifist.Sequence(unum="home", source="local", model="third", current=9).create()
            return create(model)

        self.unifist.create = inserting

        self.assertEqual(Third().generate_id(), "10:third.local:home")
        self.assertEqual(self.unifist.data["sequence"][3]["current"], 10)

        # With a SLUG it's the slug of that field, kept in the unifist source too

        self.assertEqual(Page(title="Hello, World!").generate_id(), "hello-world:page.local:home")
        self.assertEqual(self.unifist.data["slug"], {1: {"id": 1, "unum": "home", "source": "local", "model": "page", "current": "hello-world"}})

        # The same slug again adds -1, -2 and so on until it fits

        self.assertEqual(Page(title="Hello, World!").generate_id(), "hello-world-1:page.local:home")
        self.assertEqual(Page(title="hello world").generate_id(), "hello-world-2:page.local:home")
        self.assertEqual(len(self.unifist.data["slug"]), 3)

        # A list of fields makes one slug from all of them

        self.assertEqual(Person(first="Gaffer", last="Fitch").generate_id(), "gaffer-fitch:person.local:home")

        # Another model has its own slugs, so the same one doesn't clash

        self.assertEqual(Page(title="Gaffer Fitch").generate_id(), "gaffer-fitch:page.local:home")
        self.assertEqual(Person(first="Gaffer", last="Fitch").generate_id(), "gaffer-fitch-1:person.local:home")

        # Nothing to make a slug from

        with self.assertRaisesRegex(ValueError, "nothing to make a slug from"):
            Page(title="!!!").generate_id()

    def test_journal(self):

        # The id is version:identifier:resource:owner:writer, so a transaction is the same everywhere, the owner being the
        # unum in the record's id and the writer this unum. A delete is the version after the one it removes

        item = Item(name="a").create()
        item.name = "b"
        item.update()
        item.delete()

        self.assertEqual([row["id"] for row in self.journal()], [
            "1:1:item.local:home:home",
            "2:1:item.local:home:home",
            "3:1:item.local:home:home"
        ])

        # Writing on behalf of another unum, the sync say, is said with the write, and makes the id that unum's write had

        Item(id="9:item.local:away", name="c").create(writer="away")

        self.assertEqual(self.journal()[3]["id"], "1:9:item.local:away:away")
        self.assertEqual(self.journal()[3]["resource_id"], "9:item.local:away")

        # A record another unum owns that this one writes keeps its owner, and this unum is the writer

        away = Item.one("9:item.local:away").retrieve()
        away.name = "d"
        away.update()

        self.assertEqual(self.journal()[4]["id"], "2:9:item.local:away:home")

        away.name = "e"
        away.update(writer="away")

        away.delete(writer="away")

        self.assertEqual([row["id"] for row in self.journal()[5:]], ["3:9:item.local:away:away", "4:9:item.local:away:away"])

        # It goes on to each record of a bulk or a query

        Item.bulk().add(name="f").add(name="g").create(writer="away")

        self.assertEqual([row["id"] for row in self.journal()[7:]], ["1:2:item.local:home:away", "1:3:item.local:home:away"])

        Item.many(name="f").set(name="h").update(writer="away")
        Item.many(name="g").delete(writer="away")

        self.assertEqual([row["id"] for row in self.journal()[9:]], ["2:2:item.local:home:away", "2:3:item.local:home:away"])

        # And is gone after, the next write is this unum's again

        Item(name="i").create()

        self.assertEqual(self.journal()[11]["id"], "1:4:item.local:home:home")

    def test_pre(self):

        # A new record gets its id from generate_id, and starts at version 1

        item = Item(name="a").create()

        self.assertEqual(item.id, "1:item.local:home")
        self.assertEqual(item.version, 1)

        # Every update that changes something bumps the version, one that changes nothing doesn't

        item.update()

        self.assertEqual(item.version, 1)

        item.name = "b"
        item.update()

        self.assertEqual(item.version, 2)

        item.name = "c"
        item.update()

        self.assertEqual(item.version, 3)

        # A bulk create gives every record its own id

        Item.bulk().add(name="d").add(name="e").create()

        self.assertEqual(sorted(self.local.data["item"]), ["1:item.local:home", "2:item.local:home", "3:item.local:home"])

        # Retrieving is left alone

        self.assertEqual(Item.one("1:item.local:home").retrieve().name, "c")

    def test_unum(self):

        # A new record has the unum of the id it was given, this unum's for one made here

        item = Item(name="a").create()

        self.assertEqual(item.unum, "home")
        self.assertEqual(self.local.data["item"]["1:item.local:home"]["unum"], "home")

        # A record made by another unum keeps what it came with, or if that's nothing the unum in its id

        Item(id="9:item.local:away", unum="away", name="b").create(writer="away")
        Item(id="8:item.local:away", name="c").create(writer="away")

        self.assertEqual(self.local.data["item"]["9:item.local:away"]["unum"], "away")
        self.assertEqual(self.local.data["item"]["8:item.local:away"]["unum"], "away")

        # A bulk create sets it on every record

        Item.bulk().add(name="e").add(name="f").create()

        self.assertEqual(self.local.data["item"]["2:item.local:home"]["unum"], "home")
        self.assertEqual(self.local.data["item"]["3:item.local:home"]["unum"], "home")

        # It's a field like any other, so a query can name the unums it's for

        self.assertEqual(sorted(model.id for model in Item.many(unum="away").retrieve()), ["8:item.local:away", "9:item.local:away"])
        self.assertEqual(
            sorted(model.id for model in Item.many(unum__in=["home", "away"]).retrieve()),
            ["1:item.local:home", "2:item.local:home", "3:item.local:home", "8:item.local:away", "9:item.local:away"]
        )
        self.assertEqual(Item.many(unum="home").count(), 3)
        self.assertEqual(Item.many(unum="nowhere").count(), 0)

    def test_post(self):

        # A create is journaled, by the id, with when in microseconds, and the app (source) and block (model) it was in

        before = relations_unifist.microseconds()
        item = Item(name="a").create()
        after = relations_unifist.microseconds()

        self.assertEqual(len(self.journal()), 1)
        self.assertEqual(self.journal()[0]["id"], "1:1:item.local:home:home")
        self.assertEqual(self.journal()[0]["resource_id"], "1:item.local:home")
        self.assertEqual(self.journal()[0]["what"], {
            "action": "create",
            "app": "local",
            "block": "item",
            "id": "1:item.local:home",
            "after": {"id": "1:item.local:home", "version": 1, "unum": "home", "name": "a"}
        })
        self.assertTrue(before <= self.journal()[0]["when"] <= after)

        # An update is journaled with the whole record before and after, the version included

        item.name = "b"
        item.update()

        self.assertEqual(len(self.journal()), 2)
        self.assertEqual(self.journal()[1]["id"], "2:1:item.local:home:home")
        self.assertEqual(self.journal()[1]["resource_id"], "1:item.local:home")
        self.assertEqual(self.journal()[1]["what"], {
            "action": "update",
            "app": "local",
            "block": "item",
            "id": "1:item.local:home",
            "before": {"id": "1:item.local:home", "version": 1, "unum": "home", "name": "a"},
            "after": {"id": "1:item.local:home", "version": 2, "unum": "home", "name": "b"}
        })
        self.assertTrue(self.journal()[0]["when"] <= self.journal()[1]["when"])

        # An update that changes nothing isn't journaled

        item.update()

        self.assertEqual(len(self.journal()), 2)

        # A delete is journaled with the whole record it removed

        item.delete()

        self.assertEqual(len(self.journal()), 3)
        self.assertEqual(self.journal()[2]["id"], "3:1:item.local:home:home")
        self.assertEqual(self.journal()[2]["resource_id"], "1:item.local:home")
        self.assertEqual(self.journal()[2]["what"], {
            "action": "delete",
            "app": "local",
            "block": "item",
            "id": "1:item.local:home",
            "before": {"id": "1:item.local:home", "version": 2, "unum": "home", "name": "b"}
        })

        # A bulk create is journaled one record at a time

        Item.bulk().add(name="c").add(name="d").create()

        self.assertEqual([row["resource_id"] for row in self.journal()[3:]], ["2:item.local:home", "3:item.local:home"])

        # Retrieving isn't journaled

        Item.one("2:item.local:home").retrieve()

        self.assertEqual(len(self.journal()), 5)

        # Set once on the base, like the unum, JOURNAL turns it off, for the daemon say, but ids and versions still happen

        relations_unifist.UnifistModel.JOURNAL = False

        quiet = Item(name="e").create()
        quiet.name = "f"
        quiet.update()
        quiet.delete()

        self.assertEqual(quiet.id, "4:item.local:home")
        self.assertEqual(quiet.version, 2)
        self.assertEqual(len(self.journal()), 5)

    def test_create(self):

        # A bulk create is written one record at a time, each with its id and its journal row

        calls = self.counted("create")

        Item.bulk().add(name="a").add(name="b").add(name="c").create()

        self.assertEqual(len(calls), 3)
        self.assertEqual(sorted(self.local.data["item"]), ["1:item.local:home", "2:item.local:home", "3:item.local:home"])
        self.assertEqual([row["resource_id"] for row in self.journal()], ["1:item.local:home", "2:item.local:home", "3:item.local:home"])
        self.assertEqual(self.local.data["item"]["2:item.local:home"]["name"], "b")

        # Even when the chunk size makes it create as it goes

        calls.clear()

        Item.bulk(2).add(name="d").add(name="e").add(name="f").create()

        self.assertEqual(len(calls), 3)
        self.assertEqual(len(self.local.data["item"]), 6)

        # One record is just one write

        calls.clear()

        Item(name="g").create()

        self.assertEqual(len(calls), 1)

    def test_update(self):

        Item.bulk().add(name="a").add(name="a").add(name="b").create()

        # By a query, it selects, then changes and updates each record on its own

        calls = self.counted("update")

        self.assertEqual(Item.many(name="a").set(name="z").update(), 2)

        self.assertEqual(len(calls), 2)
        self.assertEqual([self.local.data["item"][id]["name"] for id in sorted(self.local.data["item"])], ["z", "z", "b"])
        self.assertEqual([self.local.data["item"][id]["version"] for id in sorted(self.local.data["item"])], [2, 2, 1])

        # Each has its own journal row, the whole record before and after

        rows = self.journal()[3:]

        self.assertEqual([row["resource_id"] for row in rows], ["1:item.local:home", "2:item.local:home"])
        self.assertEqual(rows[1]["what"], {
            "action": "update",
            "app": "local",
            "block": "item",
            "id": "2:item.local:home",
            "before": {"id": "2:item.local:home", "version": 1, "unum": "home", "name": "a"},
            "after": {"id": "2:item.local:home", "version": 2, "unum": "home", "name": "z"}
        })

        # Nothing matching is nothing done

        calls.clear()

        self.assertEqual(Item.many(name="nope").set(name="q").update(), 0)
        self.assertEqual(len(calls), 0)
        self.assertEqual(len(self.journal()), 5)

        # Records that were retrieved and changed are updated one at a time too

        items = Item.many(name="z").retrieve()
        items.name = "y"

        calls.clear()

        items.update()

        self.assertEqual(len(calls), 2)
        self.assertEqual([self.local.data["item"][id]["version"] for id in sorted(self.local.data["item"])], [3, 3, 1])
        self.assertEqual(len(self.journal()), 7)

        # One record is just one write

        calls.clear()

        item = Item.one("3:item.local:home").retrieve()
        item.name = "x"
        item.update()

        self.assertEqual(len(calls), 1)

    def test_delete(self):

        Item.bulk().add(name="a").add(name="a").add(name="b").create()

        # By a query, it selects, then deletes each record on its own

        calls = self.counted("delete")

        self.assertEqual(Item.many(name="a").delete(), 2)

        self.assertEqual(len(calls), 2)
        self.assertEqual(sorted(self.local.data["item"]), ["3:item.local:home"])

        rows = self.journal()[3:]

        self.assertEqual([row["resource_id"] for row in rows], ["1:item.local:home", "2:item.local:home"])
        self.assertEqual(rows[0]["what"], {
            "action": "delete",
            "app": "local",
            "block": "item",
            "id": "1:item.local:home",
            "before": {"id": "1:item.local:home", "version": 1, "unum": "home", "name": "a"}
        })

        # Nothing matching is nothing done

        calls.clear()

        self.assertEqual(Item.many(name="nope").delete(), 0)
        self.assertEqual(len(calls), 0)
        self.assertEqual(len(self.journal()), 5)

        # Records that were retrieved are deleted one at a time too

        Item.bulk().add(name="c").add(name="c").create()

        items = Item.many(name="c").retrieve()

        calls.clear()

        items.delete()

        self.assertEqual(len(calls), 2)
        self.assertEqual(sorted(self.local.data["item"]), ["3:item.local:home"])

        # One record is just one write

        calls.clear()

        Item.one("3:item.local:home").delete()

        self.assertEqual(len(calls), 1)
        self.assertEqual(self.local.data["item"], {})


class ServedModel(relations.Model):
    SOURCE = "TestUnifistResource"

class Jam(ServedModel):
    id = int
    name = str

class Jelly(ServedModel):
    PLURAL = "jellies"
    ID = None
    name = str

class Toast(ServedModel):
    id = int
    name = str

class Butter(ServedModel):
    id = int
    name = str

class JellyResource(relations_unifist.Resource):
    MODEL = Jelly

class ToastResource(relations_restx.Resource):
    MODEL = Toast


class TestResource(unittest.TestCase):

    def test_thy(self):

        self.assertEqual(JellyResource.thy().endpoints(), ["/model/jelly"])
        self.assertEqual(JellyResource.thy().SINGULAR, "jelly")

    def test_endpoints(self):

        class JamResource(relations_unifist.Resource):
            MODEL = Jam

        self.assertEqual(JamResource.thy().endpoints(), ["/model/jam", "/model/jam/<id>"])
        self.assertEqual(JellyResource.thy().endpoints(), ["/model/jelly"])

        self.assertEqual(relations_unifist.Resource.endpoints(ToastResource.thy()), ["/model/toast", "/model/toast/<id>"])


class TestAttach(relations.unittest.TestCase):

    maxDiff = None

    def setUp(self):

        self.source = relations.unittest.MockSource("TestUnifistResource")

        self.app = flask.Flask("unifist-api")
        self.restx = relations_restx.Api(self.app)

    def attach(self, **kwargs):

        relations_unifist.attach(
            self.restx, sys.modules[__name__], relations.models(sys.modules[__name__], ServedModel), **kwargs
        )

        return self.app.test_client()

    def test_attach(self):

        api = self.attach()

        # The models are listed, and the ones the module didn't have a resource for are made

        response = api.get("/model")

        self.assertStatusValue(response, 200, "models", [
            {
                "id": None,
                "titles": ["name"],
                "title": "Jelly",
                "singular": "jelly",
                "plural": "jellies",
                "list": ["name"]
            },
            {
                "id": "id",
                "titles": ["name"],
                "title": "Toast",
                "singular": "toast",
                "plural": "toasts",
                "list": ["id", "name"]
            },
            {
                "id": "id",
                "titles": ["name"],
                "title": "Butter",
                "singular": "butter",
                "plural": "butters",
                "list": ["id", "name"]
            },
            {
                "id": "id",
                "titles": ["name"],
                "title": "Jam",
                "singular": "jam",
                "plural": "jams",
                "list": ["id", "name"]
            }
        ])

        # Nothing's at the root but what was added there

        self.assertEqual(api.get("/jelly").status_code, 404)
        self.assertEqual(api.get("/jam").status_code, 404)
        self.assertEqual(api.get("/butter").status_code, 404)
        self.assertEqual(api.get("/toast").status_code, 404)

        # A resource of ours, one of relations_restx's and one ensure made, are all under /model

        self.assertStatusValue(api.post("/model/jelly", json={"jelly": {"name": "grape"}}), 201, "jelly", {"name": "grape"})
        self.assertStatusValue(api.get("/model/jelly"), 200, "jellies", [{"name": "grape"}])

        self.assertStatusValue(api.post("/model/toast", json={"toast": {"name": "rye"}}), 201, "toast", {"id": 1, "name": "rye"})
        self.assertStatusValue(api.get("/model/toast/1"), 200, "toast", {"id": 1, "name": "rye"})

        self.assertStatusValue(api.post("/model/jam", json={"jam": {"name": "plum"}}), 201, "jam", {"id": 1, "name": "plum"})
        self.assertStatusValue(api.get("/model/jam/1"), 200, "jam", {"id": 1, "name": "plum"})
        self.assertStatusValue(api.patch("/model/jam/1", json={"jam": {"name": "fig"}}), 202, "updated", 1)
        self.assertStatusValue(api.delete("/model/jam/1"), 202, "deleted", 1)
        self.assertEqual(api.get("/model/jam/1").status_code, 404)

        self.assertEqual(api.options("/model/jam").status_code, 200)
        self.assertEqual(api.options("/model/jam/1").status_code, 404)

        # A record needs an id to be at one

        self.assertEqual(api.get("/model/jelly/1").status_code, 404)

    def test_attach_placeholders(self):

        api = self.attach()

        # Empty lists, not a 404, until something is registered

        response = api.get("/action")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"actions": []})

        response = api.get("/view")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"views": []})

    def test_attach_actions_views(self):

        actions = [{"name": "bake"}]
        views = [{"name": "toasted"}]

        api = self.attach(actions=actions, views=views)

        self.assertStatusValue(api.get("/action"), 200, "actions", [{"name": "bake"}])
        self.assertStatusValue(api.get("/view"), 200, "views", [{"name": "toasted"}])

        # What was given isn't shared with the list served

        actions.append({"name": "burn"})
        self.assertStatusValue(api.get("/action"), 200, "actions", [{"name": "bake"}])

    def test_attach_endpoints(self):

        # A resource already attached under the name of one ensure would make isn't added again, and is still listed

        self.restx.add_resource(type("Jam", (relations_restx.Resource, ), {"MODEL": Jam}), "/custom")

        api = self.attach()

        self.assertStatusValue(api.post("/custom", json={"jam": {"name": "plum"}}), 201, "jam", {"id": 1, "name": "plum"})
        self.assertEqual(api.get("/model/jam").status_code, 404)
        self.assertIn("jam", [model["singular"] for model in api.get("/model").json["models"]])

    def test_open_api(self):

        self.attach()

        paths = self.app.test_client().get("/swagger.json").json["paths"]

        self.assertEqual(sorted(paths), [
            "/action",
            "/model",
            "/model/butter",
            "/model/butter/{id}",
            "/model/jam",
            "/model/jam/{id}",
            "/model/jelly",
            "/model/toast",
            "/model/toast/{id}",
            "/view"
        ])

        # The operations are the ones the models get anywhere else

        self.assertEqual(paths["/model/jam"]["get"]["operationId"], "jam_retrieve_many")
        self.assertEqual(paths["/model/jam"]["post"]["operationId"], "jam_create_search")
        self.assertEqual(paths["/model/jam/{id}"]["get"]["operationId"], "jam_retrieve_one")
        self.assertEqual(paths["/model/jam/{id}"]["delete"]["operationId"], "jam_delete_one")
        self.assertEqual(paths["/model/toast"]["options"]["operationId"], "toast_create_options")
        self.assertEqual(paths["/model/jelly"]["patch"]["operationId"], "jelly_update_many")
