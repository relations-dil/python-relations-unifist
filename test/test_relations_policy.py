import unittest

import relations
import relations.unittest

import relations_policy
import relations.security
import relations_unifist


class Base(relations.security.Secure, relations_unifist.UnifistModel):

    SOURCE = "app"


class Doc(Base):

    id = str
    version = int, 1
    home = str
    owner = str
    troupe = str
    title = str
    body = str


class TestPolicy(unittest.TestCase):

    maxDiff = None

    def setUp(self):

        self.unifist = relations.unittest.MockSource("unifist")
        self.policy = relations.unittest.MockSource("policy")
        self.app = relations.unittest.MockSource("app")

        relations_unifist.UnifistModel.HOME = "home"
        relations.security.POLICY = relations_policy.Policy()

        with relations.security.system():

            for name in ["pat", "sam"]:
                relations_policy.Actor(name=name).create()

            for name in ["red", "blue"]:
                relations_policy.Troupe(name=name).create()

            for actor, troupe, part in [
                ("pat:actor.policy:home", "red:troupe.policy:home", "writer"),
                ("pat:actor.policy:home", "blue:troupe.policy:home", "reader"),
                ("sam:actor.policy:home", "red:troupe.policy:home", "reader")
            ]:
                relations_policy.Casting(actor=actor, troupe=troupe, part=part).create()

            Doc([
                {"owner": "pat:actor.policy:home", "troupe": "red:troupe.policy:home", "title": "a", "body": "one"},
                {"owner": "sam:actor.policy:home", "troupe": "red:troupe.policy:home", "title": "b", "body": "two"},
                {"owner": "sam:actor.policy:home", "troupe": "blue:troupe.policy:home", "title": "c", "body": "three"}
            ]).create()

        self.pat = "pat:actor.policy:home"
        self.sam = "sam:actor.policy:home"

    def tearDown(self):

        relations_unifist.UnifistModel.HOME = None
        relations.security.POLICY = None

        for name in ["unifist", "policy", "app"]:
            del relations.SOURCES[name]

    def charter(self, **kwargs):

        with relations.security.system():
            return relations_policy.Charter(**kwargs).create()

    def titles(self, actor):

        with relations.security.acting(actor):
            return Doc.many().title

    def test_models(self):

        # They're Unifist models, global ids and a journal

        self.assertEqual(sorted(self.policy.data["actor"]), [self.pat, self.sam])
        self.assertEqual(sorted(self.policy.data["troupe"]), ["blue:troupe.policy:home", "red:troupe.policy:home"])
        self.assertEqual(sorted(self.policy.data["casting"]), ["1:casting.policy:home", "2:casting.policy:home", "3:casting.policy:home"])
        self.assertEqual(self.unifist.data["journal"]["1:pat:actor.policy:home:home"]["resource_id"], self.pat)

        charter = self.charter(model="doc", verb="retrieve", scope={"owner": "$actor"})
        self.assertEqual(charter.id, "1:charter.policy:home")
        self.assertEqual((charter.troupe, charter.part, charter.allow, charter.moves, charter.names), ("", "", True, False, []))

    def test_no_charter(self):

        self.charter(model="nope", verb="retrieve")

        with relations.security.acting(self.pat):
            self.assertRaisesRegex(relations.security.Denied, "doc: cannot retrieve", Doc.many().retrieve)

    def test_actor(self):

        self.charter(model="doc", verb="retrieve", scope={"owner": "$actor"})

        self.assertEqual(self.titles(self.pat), ["a"])
        self.assertEqual(self.titles(self.sam), ["b", "c"])

        # The actor can be the record

        with relations.security.system():
            actor = relations_policy.Actor.one(name="pat").retrieve()

        self.assertEqual(self.titles(actor), ["a"])

        # and a charter for no troupe or part is for anyone, cast or not, so they get what is theirs, which is nothing

        self.assertEqual(self.titles("nobody"), [])

    def test_troupes(self):

        self.charter(model="doc", verb="retrieve", scope={"troupe__in": "$troupes"})

        self.assertEqual(self.titles(self.pat), ["a", "b", "c"])
        self.assertEqual(self.titles(self.sam), ["a", "b"])

    def test_who(self):

        # By the troupe and part cast, or either, or anyone

        self.charter(troupe="red:troupe.policy:home", part="writer", model="doc", verb="retrieve", scope={"title": "a"})
        self.assertEqual(self.titles(self.pat), ["a"])
        self.assertRaises(relations.security.Denied, self.titles, self.sam)

        self.charter(part="reader", model="doc", verb="retrieve", scope={"title": "b"})
        self.assertEqual(self.titles(self.pat), ["a"])  # The more specific
        self.assertEqual(self.titles(self.sam), ["b"])

        self.charter(troupe="blue:troupe.policy:home", model="doc", verb="retrieve", scope={"title": "c"})
        self.assertEqual(self.titles(self.sam), ["b"])  # Not cast in blue

        self.charter(model="doc", verb="retrieve", scope={"title": "c"})
        self.assertEqual(self.titles("nobody"), ["c"])  # Anyone

    def test_specific(self):

        self.charter(scope={"title": "a"})
        self.assertEqual(self.titles(self.pat), ["a"])  # Any model and verb

        self.charter(model="doc", scope={"title": "b"})
        self.assertEqual(self.titles(self.pat), ["b"])  # A model over any

        self.charter(model="doc", verb="retrieve", scope={"title": "c"})
        self.assertEqual(self.titles(self.pat), ["c"])  # A verb over any

        # count and titles are retrieve's unless they have their own

        with relations.security.acting(self.pat):
            self.assertEqual(Doc.many().count(), 1)

        self.charter(model="doc", verb="count", scope={})

        with relations.security.acting(self.pat):
            self.assertEqual(Doc.many().count(), 3)
            self.assertEqual(Doc.many().title, ["c"])

    def test_deny(self):

        self.charter(model="doc", scope={})
        self.assertEqual(self.titles(self.pat), ["a", "b", "c"])

        # A more specific charter can take it away, or give it back

        self.charter(part="reader", model="doc", verb="retrieve", allow=False)
        self.assertRaises(relations.security.Denied, self.titles, self.sam)

        self.charter(troupe="red:troupe.policy:home", part="reader", model="doc", verb="retrieve", scope={"title": "b"})
        self.assertEqual(self.titles(self.sam), ["b"])

    def test_tie(self):

        # Both parts of pat's are as specific, and say different things

        self.charter(part="writer", model="doc", verb="retrieve", scope={"title": "a"})
        self.charter(part="reader", model="doc", verb="retrieve", scope={"title": "b"})

        self.assertRaisesRegex(relations.security.Denied, "charters tie with different rules for retrieve", self.titles, self.pat)

        # But not if they say the same

        with relations.security.system():
            relations_policy.Charter.one(part="reader", model="doc").retrieve().set(scope={"title": "a"}).update()

        self.assertEqual(self.titles(self.pat), ["a"])

    def test_write(self):

        self.charter(model="doc", verb="retrieve", scope={"troupe__in": "$troupes"})
        self.charter(part="writer", model="doc", verb="create", scope={"owner": "$actor"}, pins={"troupe": "red:troupe.policy:home"})
        self.charter(part="writer", model="doc", verb="update", scope={"owner": "$actor"}, names=["title", "body"])

        with relations.security.acting(self.pat):

            doc = Doc(owner=self.pat, troupe="blue:troupe.policy:home", title="d").create()
            self.assertEqual(doc.troupe, "red:troupe.policy:home")

            doc = Doc.one(title="a").retrieve()
            doc.body = "uno"
            self.assertEqual(doc.update(), 1)

            doc.troupe = "blue:troupe.policy:home"
            self.assertRaisesRegex(relations.security.Denied, "cannot write troupe", doc.update)

            self.assertRaises(relations.security.Denied, Doc(owner=self.sam, title="e").create)
            self.assertRaises(relations.security.Denied, Doc.one(title="a").delete)

    def test_moves(self):

        self.charter(model="doc", verb="retrieve", scope={"owner": "$actor"})
        self.charter(model="doc", verb="update", scope={"owner": "$actor"})
        self.charter(model="doc", verb="delete", scope={"owner": "$actor"}, moves=True, becomes={})

        with relations.security.acting(self.pat):

            doc = Doc.one(title="a").retrieve()
            doc.owner = self.sam
            self.assertRaisesRegex(relations.security.Denied, "to that", doc.update)

        self.charter(part="writer", model="doc", verb="update", scope={"owner": "$actor"}, moves=True, becomes={})

        with relations.security.acting(self.pat):

            doc = Doc.one(title="a").retrieve()
            doc.owner = self.sam
            self.assertEqual(doc.update(), 1)
            self.assertRaises(relations.security.Denied, getattr, doc, "title")

    def test_cache(self):

        self.charter(model="doc", verb="retrieve", scope={"owner": "$actor"})

        calls = []
        real = self.policy.retrieve

        def counting(model, *args, **kwargs):
            calls.append(model.NAME)
            return real(model, *args, **kwargs)

        self.policy.retrieve = counting

        with relations.security.acting(self.pat):
            Doc.many().retrieve()
            Doc.many().count()
            Doc.many().retrieve()

        # Casting, then charter, for retrieve, then count, which is retrieve's, and once each

        self.assertEqual(calls, ["casting", "charter", "casting", "charter"])

        # but not kept after

        with relations.security.acting(self.pat):
            Doc.many().retrieve()

        self.assertEqual(len(calls), 6)

    def test_outside(self):

        # No acting to keep them in, so they're looked up each time

        self.charter(model="doc", verb="retrieve", scope={})

        rule = relations_policy.Policy().rule(self.pat, Doc(), "retrieve")

        self.assertTrue(rule.allow)
        self.assertEqual(rule.scope, {})
        self.assertIsNone(rule.into)
        self.assertIsNone(rule.fields)

    def test_expand(self):

        self.assertEqual(
            relations_policy.expand({"a": ["$actor", "x"], "b": {"c": "$troupes"}, "d": 1}, "pat", ["red"]),
            {"a": ["pat", "x"], "b": {"c": ["red"]}, "d": 1}
        )
