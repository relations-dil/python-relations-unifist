"""
Relations Policy Module
"""

import json

import relations
import relations.security
import relations_unifist


def blank():
    """
    A string column that is never None, blank meaning any when it's matched
    """

    return relations.Field(str, default="", none=False)


class PolicyBase(relations_unifist.UnifistModel):
    """
    The base of the tables policy is kept in, whose source is set here, at run time, by whatever uses them (the
    default is policy). They're Unifist models, so they have ids, versions and the journal like any other record,
    and can be routed and synced as any other. They aren't Secure, which is how a policy reads its own rules
    """

    SOURCE = "policy"


class Actor(PolicyBase):
    """
    Who acts. Its id is what is given to acting
    """

    id = str
    version = int, 1
    home = str
    name = str

    SLUG = "name"
    TITLES = ["name"]
    UNIQUE = ["name"]


class Troupe(PolicyBase):
    """
    A group of actors
    """

    id = str
    version = int, 1
    home = str
    name = str

    SLUG = "name"
    TITLES = ["name"]
    UNIQUE = ["name"]


class Casting(PolicyBase):
    """
    An actor cast in a troupe, in a part
    """

    id = str
    version = int, 1
    home = str
    actor = str
    troupe = str
    part = str

    UNIQUE = ["actor", "troupe", "part"]
    INDEX = ["actor"]


class Charter(PolicyBase):
    """
    What a part may do with a verb on a model, in a troupe or any, the rule being for the actors cast in it.
    A blank troupe, part, model or verb is any, and the most specific charter that matches an actor, model
    and verb is the one that gives the rule. Not allowing is a rule too, and a more specific charter can allow
    what a less specific one doesn't.

    scope, becomes and pins are filter kwargs, and fields (the names that can be read or written, none meaning
    all) a list, where a string of $actor is the actor's id and $troupes the ids of the troupes they're cast
    in. becomes is what new values have to satisfy only if moves, else it's the scope, and {} lets a record be
    moved out of reach
    """

    id = str
    version = int, 1
    home = str
    troupe = blank()
    part = blank()
    model = blank()
    verb = blank()
    allow = bool, True
    scope = dict
    moves = bool, False
    becomes = dict
    pins = dict
    names = list

    UNIQUE = ["troupe", "part", "model", "verb"]
    INDEX = ["part"]


def expand(value, actor, troupes):
    """
    Fills in $actor and $troupes wherever a value is exactly one of them
    """

    if value == "$actor":
        return actor

    if value == "$troupes":
        return list(troupes)

    if isinstance(value, dict):
        return {name: expand(each, actor, troupes) for name, each in value.items()}

    if isinstance(value, list):
        return [expand(each, actor, troupes) for each in value]

    return value


class Policy(relations.security.Policy):
    """
    Rules from the charters of the troupes the actor is cast in, kept for as long as the actor is acting
    """

    @staticmethod
    def score(charter, verb):
        """
        How specific a charter is, the model then the verb then who it's for, a verb that is the one asked for
        being more than the one it inherits, and that more than any
        """

        return (
            1 if charter.model else 0,
            0 if not charter.verb else 2 if charter.verb == verb else 1,
            (1 if charter.troupe else 0) + (1 if charter.part else 0)
        )

    @staticmethod
    def fingerprint(charter):
        """
        What makes a charter's rule, to tell if two that tie would give different ones
        """

        return json.dumps([
            charter.allow, charter.scope, charter.moves, charter.becomes, charter.pins, charter.names
        ], sort_keys=True)

    def rule(self, actor, model, verb):
        """
        The rule for the actor to do the verb on the model, None if no charter gives one, and Denied if the
        most specific charters that do tie with different rules
        """

        actor = getattr(actor, "id", actor)

        kept = relations.security.cache()
        key = (actor, model.NAME, verb)

        if kept is not None and key in kept:
            return kept[key]

        verbs = [verb, self.INHERIT.get(verb)]

        with relations.security.system():

            castings = {(casting.troupe, casting.part) for casting in Casting.many(actor=actor).retrieve()}
            charters = list(Charter.many(model__in=["", model.NAME], verb__in=["", *[each for each in verbs if each]]).retrieve())

        troupes = sorted({troupe for troupe, _ in castings})
        parts = {part for _, part in castings}

        def applies(charter):
            if charter.troupe and charter.part:
                return (charter.troupe, charter.part) in castings
            if charter.troupe:
                return charter.troupe in troupes
            if charter.part:
                return charter.part in parts
            return True

        charters = [charter for charter in charters if applies(charter)]

        rule = None

        if charters:

            best = max(self.score(charter, verb) for charter in charters)
            charters = [charter for charter in charters if self.score(charter, verb) == best]

            if len({self.fingerprint(charter) for charter in charters}) > 1:
                raise relations.security.Denied(model, f"charters tie with different rules for {verb}")

            charter = charters[0]

            rule = relations.security.Rule(
                allow=charter.allow,
                scope=expand(charter.scope, actor, troupes),
                into=expand(charter.becomes, actor, troupes) if charter.moves else None,
                force=expand(charter.pins, actor, troupes),
                fields=list(charter.names) or None
            )

        if kept is not None:
            kept[key] = rule

        return rule
