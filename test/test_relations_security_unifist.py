import unittest

import relations
import relations.unittest

import relations.security
import relations_unifist


class Base(relations.security.Secure, relations_unifist.UnifistModel):

    SOURCE = "local"


class Doc(Base):

    id = str
    version = int, 1
    unum = str
    owner = str
    title = str
    body = str
    locked = bool, False


def mine(actor):
    return {"owner": actor}


def policy(**rules):

    verbs = {
        "retrieve": relations.security.Rule(scope=mine),
        "create": relations.security.Rule(scope=mine),
        "update": relations.security.Rule(scope=lambda actor: {"owner": actor, "locked": False}, into=mine),
        "delete": relations.security.Rule(scope=lambda actor: {"owner": actor, "locked": False})
    }

    verbs.update(rules)

    return relations.security.Policy({"doc": verbs})


class TestSecureUnifist(unittest.TestCase):

    maxDiff = None

    def setUp(self):

        self.unifist = relations.unittest.MockSource("unifist")
        self.local = relations.unittest.MockSource("local")

        relations_unifist.UnifistModel.UNUM = "home"
        relations.security.POLICY = policy()

        with relations.security.system():
            Doc([
                {"owner": "pat", "title": "a", "body": "one"},
                {"owner": "pat", "title": "b", "body": "two", "locked": True},
                {"owner": "sam", "title": "c", "body": "three"}
            ]).create()

        self.before = len(self.journal())

    def tearDown(self):

        relations_unifist.UnifistModel.UNUM = None
        relations.security.POLICY = None

        del relations.SOURCES["unifist"]
        del relations.SOURCES["local"]

    def journal(self):

        return list(self.unifist.data["journal"].values())

    def docs(self):

        with relations.security.system():
            return {doc.title: doc for doc in Doc.many().retrieve()}

    def test_setup(self):

        # Made as the code, so ids, versions and the journal are as they were

        self.assertEqual(sorted(self.local.data["doc"]), ["1:doc.local:home", "2:doc.local:home", "3:doc.local:home"])
        self.assertEqual(self.before, 3)

    def test_create(self):

        with relations.security.acting("pat"):

            doc = Doc(owner="pat", title="d").create()
            self.assertEqual(doc.id, "4:doc.local:home")
            self.assertEqual(doc.version, 1)

            self.assertRaises(relations.security.Denied, Doc(owner="sam", title="e").create)

        # What was denied was never given an id or journaled

        self.assertEqual(len(self.journal()), self.before + 1)
        self.assertEqual(self.unifist.data["sequence"][1]["current"], 4)

    def test_update_by_query(self):

        with relations.security.acting("pat"):
            self.assertEqual(Doc.many().set(body="all").update(), 1)

        docs = self.docs()

        self.assertEqual([docs[title].body for title in "abc"], ["all", "two", "three"])
        self.assertEqual([docs[title].version for title in "abc"], [2, 1, 1])

        # One journal row for each record changed, and only those

        journal = self.journal()[self.before:]

        self.assertEqual([row["resource_id"] for row in journal], ["1:doc.local:home"])
        self.assertEqual(journal[0]["what"]["before"]["body"], "one")
        self.assertEqual(journal[0]["what"]["after"]["body"], "all")

    def test_delete_by_query(self):

        with relations.security.acting("pat"):
            self.assertEqual(Doc.many().delete(), 1)

        self.assertEqual(sorted(self.docs()), ["b", "c"])
        self.assertEqual([row["what"]["action"] for row in self.journal()[self.before:]], ["delete"])

    def test_denied_by_record(self):

        with relations.security.acting("pat"):

            doc = Doc.one(title="b").retrieve()
            doc.body = "dos"
            self.assertRaises(relations.security.Denied, doc.update)

            self.assertRaises(relations.NotFoundError, Doc.one(title="c").delete)

        self.assertEqual(len(self.journal()), self.before)

    def test_fields(self):

        # What the actor can't read still has an id and a version, and the journal has all of it

        relations.security.POLICY = policy(retrieve=relations.security.Rule(scope=mine, fields=["owner", "title"]))

        with relations.security.acting("pat"):

            docs = Doc.many().retrieve()

            self.assertEqual(docs.title, ["a", "b"])
            self.assertEqual(docs.export(), [{"owner": "pat", "title": "a"}, {"owner": "pat", "title": "b"}])
            self.assertRaisesRegex(relations.security.Denied, "cannot read id", getattr, docs[0], "id")

            self.assertEqual(Doc.many(title="a").set(body="all").update(), 1)

        self.assertEqual(self.docs()["a"].version, 2)

        journal = self.journal()[self.before:]

        self.assertEqual(journal[0]["what"]["after"]["body"], "all")
        self.assertEqual(journal[0]["what"]["after"]["id"], "1:doc.local:home")

    def test_transfer(self):

        relations.security.POLICY = policy(update=relations.security.Rule(scope=mine, into={}))

        with relations.security.acting("pat"):

            doc = Doc.one(title="a").retrieve()
            doc.owner = "sam"
            self.assertEqual(doc.update(), 1)

            self.assertRaisesRegex(relations.security.Denied, "no longer yours to read", getattr, doc, "title")

        self.assertEqual(self.docs()["a"].owner, "sam")

        journal = self.journal()[self.before:]

        self.assertEqual(journal[0]["what"]["before"]["owner"], "pat")
        self.assertEqual(journal[0]["what"]["after"]["owner"], "sam")

    def test_transfer_by_query(self):

        relations.security.POLICY = policy(update=relations.security.Rule(scope=mine, into={}))

        with relations.security.acting("pat"):
            self.assertEqual(Doc.many().set(owner="sam").update(), 2)
            self.assertEqual(Doc.many().count(), 0)

        self.assertEqual([doc.owner for doc in self.docs().values()], ["sam", "sam", "sam"])
        self.assertEqual(len(self.journal()), self.before + 2)
