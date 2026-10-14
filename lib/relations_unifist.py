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


class Sequence(relations.Model):
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


class Slug(relations.Model):
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


class Journal(relations.Model):
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
