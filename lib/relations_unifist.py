"""
Main Relations Unifist Module
"""

import re
import time
import unicodedata

import relations


def slugify(titles, length=32):
    """
    Makes a slug from a name or a list of titles in the style of a dns label: lower case letters and
    digits joined by single dashes, accents folded to plain letters, anything else dropped. It is cut to
    length (1 to 255, what a string holds) at the last dash within it, or at length if there isn't one.
    Raises a ValueError if nothing is left to make one from.
    """

    if not 1 <= length <= 255:
        raise ValueError("length has to be from 1 to 255")

    if isinstance(titles, (list, tuple)):
        titles = " ".join(str(title) for title in titles if title is not None)

    folded = unicodedata.normalize("NFKD", str(titles or "")).encode("ascii", "ignore").decode("ascii")

    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")

    if len(slug) > length:
        slug = slug[:length + 1]
        slug = slug[:slug.rindex("-")] if "-" in slug else slug[:length]

    if not slug:
        raise ValueError("nothing to make a slug from")

    return slug


def microseconds():
    """
    Now, as an int of microseconds since the Unix epoch, how every time is stored
    """

    return time.time_ns() // 1000


class UnifistBase(relations.Model):
    """
    The base of the tables kept in the Unifist source, whose name is set here, at run time, by whatever
    uses them (the default is unifist)
    """

    SOURCE = "unifist"


class Sequence(UnifistBase):
    """
    A counter, one per unum, source and model. Taking n ids moves current up by n
    """

    id = int
    unum = str, False
    source = str, False
    model = str, False
    current = int, 0

    TITLES = ["unum", "source", "model"]
    UNIQUE = ["unum", "source", "model"]


class Slug(UnifistBase):
    """
    A slug that is taken, one row per slug for a unum, source and model
    """

    id = int
    unum = str, False
    source = str, False
    model = str, False
    current = str, False

    TITLES = ["unum", "source", "model", "current"]
    UNIQUE = ["unum", "source", "model", "current"]


class Journal(UnifistBase):
    """
    Every change, what was created, or the before and after of an update, or what a delete removed
    """

    id = int
    resource_id = str, False
    when = microseconds
    what = dict, False

    TITLES = ["resource_id"]
    UNIQUE = {}
    INDEX = ["resource_id"]


class UnifistModel(relations.Model):
    """
    The base of models whose ids come from a Unifist source, a regular source holding the sequence, slug and
    journal tables, named by UnifistBase.SOURCE. UNUM names the unum, set on the model like SOURCE is
    """

    UNUM = None     # Name of the unum
    SLUG = None     # Whether to use other fields for id
    JOURNAL = True  # Whether or not to Journal

    _journaling = None  # What pre keeps for post to journal

    def __init__(self, *args, **kwargs):
        """
        Checks the model has what ids and versions need, then does what any model does
        """

        identity = self.thy()
        names = identity._fields._names # pylint: disable=protected-access

        if "id" not in names or names["id"].kind is not str:
            raise relations.ModelError(identity, "id has to be a str field")

        if "version" not in names or names["version"].kind is not int:
            raise relations.ModelError(identity, "version has to be an int field")

        if self.SLUG is not None:
            for name in self.SLUG if isinstance(self.SLUG, list) else [self.SLUG]:
                if name not in names:
                    raise relations.ModelError(identity, f"SLUG field {name} not found")

        super().__init__(*args, **kwargs)

    def generate_id(self):
        """
        Makes the id for a new record: current.model.source.unum. Without a SLUG the current is the next
        number from the Sequence, which moves up only where it still holds what was just read, so nothing is
        given out twice, and is inserted the first time. With a SLUG the current is the slug of the field, or
        the list of fields, tried in the Slug table, with -1, -2 and so on added until one isn't taken. Either
        race that's lost is tried again
        """

        current = None

        if self.SLUG is None:

            while True:

                found = Sequence.one(unum=self.UNUM, source=self.SOURCE, model=self.NAME).retrieve(False)

                if not found:

                    current = 1

                    try:

                        Sequence(unum=self.UNUM, source=self.SOURCE, model=self.NAME, current=current).create()
                        break

                    except relations.UniqueError:
                        continue

                current = found.current + 1

                if Sequence.many(
                    unum=self.UNUM, source=self.SOURCE, model=self.NAME, current=found.current
                ).set(
                    current=current
                ).update():
                    break

        else:

            fields = self.SLUG if isinstance(self.SLUG, list) else [self.SLUG]

            slug = current = slugify([self[field] for field in fields])
            tries = 0

            while True:

                try:
                    current = Slug(
                        unum=self.UNUM, source=self.SOURCE, model=self.NAME, current=current
                    ).create().current
                    break
                except relations.UniqueError:
                    tries += 1
                    current = f"{slug}-{tries}"
                    continue

        return f"{current}.{self.NAME}.{self.SOURCE}.{self.UNUM}"

    def journal(self, action, model, before=None):
        """
        Writes a Journal row for a record that was created, updated or deleted, with the app (source) and
        block (model) it was in, the id, and the whole record before and after as the action makes sense
        """

        what = {
            "action": action,
            "app": model.SOURCE,
            "block": model.NAME,
            "id": model.id
        }

        if action == "create":
            what["after"] = model.export()
        elif action == "update":
            what["before"] = before
            what["after"] = model.export()
        else:
            what["before"] = before

        Journal(resource_id=model.id, what=what).create()

    def create(self, *args, **kwargs):
        """
        Creates one record at a time, each with its own hooks, so a bulk create is a write for every record
        """

        if not self._bulk:
            return super().create(*args, **kwargs)

        for model in self._models or []:
            model.create(*args, **kwargs)

        self._models = []

        return self

    def update(self, *args, **kwargs):
        """
        Updates one record at a time, each with its own hooks. By a query it selects the records first, then
        sets what was set on each of them. Returns how many were updated
        """

        by_query = self._action == "retrieve" and self._mode == "many"

        if by_query:

            values = {field.name: field.value for field in self._record._order if field.changed} # pylint: disable=protected-access

            self.retrieve()

            for model in self._models or []:
                model.set(**values)

        if by_query or self._models:
            return sum(model.update(*args, **kwargs) for model in self._models or [])

        return super().update(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Deletes one record at a time, each with its own hooks. By a query it selects the records first.
        Returns how many were deleted
        """

        by_query = self._action == "retrieve" and self._mode == "many"

        if by_query:
            self.retrieve()

        if by_query or self._models:
            return sum(model.delete(*args, **kwargs) for model in self._models or [])

        return super().delete(*args, **kwargs)

    def pre(self, action, *args, **kwargs):
        """
        Gives new records their ids, bumps the version of records that changed, and keeps what post
        needs to journal
        """

        self._journaling = []

        for model in self._each("create" if action == "create" else "update"):

            if action == "create":

                if model.id is None:
                    model.id = model.generate_id()

                self._journaling.append((model, None))

            elif action == "update" and any(field.delta() for field in model._record._order): # pylint: disable=protected-access

                self._journaling.append((model, {field.name: field.original for field in model._record._order})) # pylint: disable=protected-access
                model.version = model.version + 1

            elif action == "delete":

                self._journaling.append((model, model.export()))

    def post(self, action, result, *args, **kwargs):
        """
        Journals what pre kept, if the model is to be journaled
        """

        if self.JOURNAL:
            for model, before in self._journaling:
                self.journal(action, model, before)

        self._journaling = []

        return result
