"""
Main Relations Unifist Module
"""

import re
import time
import unicodedata

import flask_restx

import relations
import relations_restx


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
    A counter, one per home, source and model. Taking n ids moves current up by n
    """

    id = int
    home = str, False, {"length": 64}
    source = str, False, {"length": 64}
    model = str, False, {"length": 64}
    current = int, 0

    TITLES = ["home", "source", "model"]
    UNIQUE = ["home", "source", "model"]


class Slug(UnifistBase):
    """
    A slug that is taken, one row per slug for a home, source and model
    """

    id = int
    home = str, False, {"length": 64}
    source = str, False, {"length": 64}
    model = str, False, {"length": 64}
    current = str, False

    TITLES = ["home", "source", "model", "current"]
    UNIQUE = ["home", "source", "model", "current"]


class Journal(UnifistBase):
    """
    Every change, what was created, or the before and after of an update, or what a delete removed. The id
    is the transaction, version:identifier:resource:owner:writer, the same in every unum it's written to
    """

    id = str
    resource_id = str, False
    when = microseconds
    what = dict, False

    TITLES = ["resource_id"]
    UNIQUE = {}
    INDEX = ["resource_id"]


class UnifistModel(relations.Model):
    """
    The base of models whose ids come from a Unifist source, a regular source holding the sequence, slug and
    journal tables. UNIFIST names that source, unifist unless changed, and HOME names the unum the records are
    at home in, this one, both set on the app's own base model like SOURCE is, and the app makes its source with
    that name. A model has the home of its id, the unum that made the record, as a regular str field, so a
    query can name the homes it's for
    """

    UNIFIST = "unifist"  # Name of the Unifist source, a different source than the app's
    HOME = None     # Name of the unum records are at home in, this one
    SLUG = None     # Whether to use other fields for id
    JOURNAL = True  # Whether or not to Journal

    _journaling = None  # What pre keeps for post to journal
    _writer = None      # The unum writing, if on behalf of another, kept for post

    def __init_subclass__(cls, **kwargs):
        """
        A model with a SLUG and no TITLES of its own is titled by the SLUG fields and then the home, so a record is
        called by its name and where it's from, not by its whole id, which is what a supplied id is titled by. That
        changes only the titles: the unique indexes of a model with a supplied id default to none, so no table changes
        """

        super().__init_subclass__(**kwargs)

        slugs = cls.SLUG if isinstance(cls.SLUG, list) else [cls.SLUG]

        # A SLUG naming a field the model doesn't have is left for __init__ to say so, which says it better

        if cls.TITLES is None and cls.SLUG is not None and all(slug in vars(cls) for slug in slugs):
            cls.TITLES = [*slugs, "home"]

    def __init__(self, *args, **kwargs):
        """
        Checks the model has what ids, versions and homes need, then does what any model does
        """

        identity = self.thy()
        names = identity._fields._names # pylint: disable=protected-access

        if "id" not in names or names["id"].kind is not str:
            raise relations.ModelError(identity, "id has to be a str field")

        if "version" not in names or names["version"].kind is not int:
            raise relations.ModelError(identity, "version has to be an int field")

        if "home" not in names or names["home"].kind is not str:
            raise relations.ModelError(identity, "home has to be a str field")

        if self.SLUG is not None:
            for name in self.SLUG if isinstance(self.SLUG, list) else [self.SLUG]:
                if name not in names:
                    raise relations.ModelError(identity, f"SLUG field {name} not found")

        super().__init__(*args, **kwargs)

    def generate_id(self):
        """
        Makes the id for a new record: current:model.source:home. Without a SLUG the current is the next
        number from the Sequence, which moves up only where it still holds what was just read, so nothing is
        given out twice, and is inserted the first time. With a SLUG the current is the slug of the field, or
        the list of fields, tried in the Slug table, with -1, -2 and so on added until one isn't taken. Either
        race that's lost is tried again
        """

        current = None

        if self.SLUG is None:

            while True:

                found = Sequence.one(home=self.HOME, source=self.SOURCE, model=self.NAME).retrieve(False)

                if not found:

                    current = 1

                    try:

                        Sequence(home=self.HOME, source=self.SOURCE, model=self.NAME, current=current).create()
                        break

                    except relations.UniqueError:
                        continue

                current = found.current + 1

                if Sequence.many(
                    home=self.HOME, source=self.SOURCE, model=self.NAME, current=found.current
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
                        home=self.HOME, source=self.SOURCE, model=self.NAME, current=current
                    ).create().current
                    break
                except relations.UniqueError:
                    tries += 1
                    current = f"{slug}-{tries}"
                    continue

        return f"{current}:{self.NAME}.{self.SOURCE}:{self.HOME}"

    def journal(self, action, model, before=None):
        """
        Writes a Journal row for a record that was created, updated or deleted, with the app (source) and
        block (model) it was in, the id, and the whole record before and after as the action makes sense.
        Its id is version:identifier:resource:owner:writer, the version being the one after the write (a
        delete's is the one after the version it removes), the owner the unum in the record's id, and the
        writer this unum unless the write said it was on behalf of another
        """

        identifier, resource, owner = model.id.split(":", 2)

        version = before["version"] + 1 if action == "delete" else model.version

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

        Journal(
            id=f"{version}:{identifier}:{resource}:{owner}:{self._writer or self.HOME}",
            resource_id=model.id,
            what=what
        ).create()

    def create(self, *args, writer=None, **kwargs):
        """
        Creates one record at a time, each with its own hooks, so a bulk create is a write for every record.
        The writer is the unum writing, this unum unless it's on behalf of another
        """

        self._writer = writer

        if not self._bulk:
            return super().create(*args, **kwargs)

        for model in self._models or []:
            model.create(*args, writer=writer, **kwargs)

        self._models = []

        return self

    def update(self, *args, writer=None, **kwargs):
        """
        Updates one record at a time, each with its own hooks. By a query it selects the records first, then
        sets what was set on each of them. Returns how many were updated. The writer is the unum writing,
        this unum unless it's on behalf of another
        """

        self._writer = writer

        by_query = self._action == "retrieve" and self._mode == "many"

        if by_query:

            values = {field.name: field.value for field in self._record._order if field.changed} # pylint: disable=protected-access

            self.retrieve()

            for model in self._models or []:
                model.set(**values)

        if by_query or self._models:
            return sum(model.update(*args, writer=writer, **kwargs) for model in self._models or [])

        return super().update(*args, **kwargs)

    def delete(self, *args, writer=None, **kwargs):
        """
        Deletes one record at a time, each with its own hooks. By a query it selects the records first.
        Returns how many were deleted. The writer is the unum writing, this unum unless it's on behalf of another
        """

        self._writer = writer

        by_query = self._action == "retrieve" and self._mode == "many"

        if by_query:
            self.retrieve()

        if by_query or self._models:
            return sum(model.delete(*args, writer=writer, **kwargs) for model in self._models or [])

        return super().delete(*args, **kwargs)

    def pre(self, action, *args, **kwargs):
        """
        Gives new records their ids and the home in them, bumps the version of records that changed, and keeps
        what post needs to journal
        """

        self._journaling = []

        for model in self._each("create" if action == "create" else "update"):

            if action == "create":

                if model.id is None:
                    model.id = model.generate_id()

                if model.home is None:
                    model.home = model.id.split(":", 2)[2]

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


class Resource(relations_restx.Resource):
    """
    A relations_restx Resource that serves its model under /model, /model/{singular} and /model/{singular}/<id>
    """

    @classmethod
    def thy(cls, self=None):
        """
        Makes the shell of an instance from this class, so thy().endpoints() is this class's, not the base's
        """

        if self is None:
            self = object.__new__(cls)

        return super().thy(self)

    def endpoints(self):
        """
        Lists the endpoints this resource has, under /model
        """

        endpoints = [f"/model/{self.SINGULAR}"]

        if self._model.ID is not None:
            endpoints.append(f"/model/{self.SINGULAR}/<id>")

        return endpoints


def attach(restx, module, models, actions=None, views=None):
    """
    Attach all Resources to a RestX under /model, whatever they subclass (the ones ensure makes are
    relations_restx's), with GET /model listing the models, GET /action the actions and GET /view the views,
    both empty unless given
    """

    class Model(flask_restx.Resource):
        """
        Custom class for each call
        """

        MODELS = []

        def get(self):
            """
            List all models
            """
            return {"models": self.MODELS}

    class Action(flask_restx.Resource):
        """
        Custom class for each call
        """

        ACTIONS = list(actions or [])

        def get(self):
            """
            List all actions
            """
            return {"actions": self.ACTIONS}

    class View(flask_restx.Resource):
        """
        Custom class for each call
        """

        VIEWS = list(views or [])

        def get(self):
            """
            List all views
            """
            return {"views": self.VIEWS}

    restx.add_resource(Model, "/model")
    restx.add_resource(Action, "/action")
    restx.add_resource(View, "/view")

    for resource in relations_restx.resources(module) + relations_restx.ensure(module, models):

        thy = resource.thy()

        Model.MODELS.append({
            "id": thy._model._id,
            "titles": thy._model._titles,
            "title": thy._model.TITLE,
            "singular": thy.SINGULAR,
            "plural": thy.PLURAL,
            "list": thy.LIST
        })

        if resource.__name__.lower() not in restx.endpoints:
            restx.add_resource(resource, *Resource.endpoints(thy))
