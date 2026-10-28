"""
The keys of the Unifist tables have to fit every source. What limits them is MySQL, where a key can be 3072
bytes, 4 for each character of utf8mb4, so home, source and model are 64 characters, not 255
"""

import os
import re
import shutil
import sqlite3
import tempfile
import unittest

import relations_psycopg2
import relations_pymysql
import relations_sqlite3

import relations_unifist

KEY_BYTES = 3072
CHARACTER_BYTES = 4
CAPPED = ["home", "source", "model"]
MODELS = [relations_unifist.Sequence, relations_unifist.Slug]

COLUMN = re.compile(r'[`"](\w+)[`"] VARCHAR\((\d+)\)')
UNIQUE = re.compile(r'UNIQUE [`"][\w-]+[`"] \(([^)]*)\)')


def columns(sql):
    """
    The VARCHAR lengths of a table's columns, by name
    """

    return {name: int(length) for name, length in COLUMN.findall(sql)}


def uniques(sql):
    """
    The columns in each unique key of a table
    """

    return [re.findall(r'\w+', names) for names in UNIQUE.findall(sql)]


class TestMySQL(unittest.TestCase):
    """
    pymysql, whose table definitions are made by relations-mysql
    """

    maxDiff = None

    def setUp(self):

        self.source = relations_pymysql.Source("unifist-pymysql", schema="unifist", connection=False)

    def test_length(self):

        for model in MODELS:

            sql = self.source.define(model.thy().define())
            sizes = columns(sql)

            for name in CAPPED:
                self.assertEqual(sizes[name], 64, f"{model.NAME}.{name}")

    def test_key(self):

        for model in MODELS:

            sql = self.source.define(model.thy().define())
            sizes = columns(sql)
            keys = uniques(sql)

            self.assertTrue(keys, model.NAME)

            for key in keys:
                self.assertLessEqual(
                    sum(sizes[name] for name in key) * CHARACTER_BYTES, KEY_BYTES, f"{model.NAME} {key}"
                )


class TestPostgreSQL(unittest.TestCase):
    """
    psycopg2, whose table definitions are made by relations-postgresql
    """

    maxDiff = None

    def setUp(self):

        self.source = relations_psycopg2.Source("unifist-psycopg2", "unifist", schema="unifist", connection=False)

    def test_length(self):

        for model in MODELS:

            sql = self.source.define(model.thy().define())
            sizes = columns(sql)

            for name in CAPPED:
                self.assertEqual(sizes[name], 64, f"{model.NAME}.{name}")


class TestSQLite(unittest.TestCase):
    """
    sqlite3, whose table definitions are made by relations-sqlite and which holds the length with a CHECK
    """

    maxDiff = None

    def setUp(self):

        self.directory = tempfile.mkdtemp()

        self.source = relations_sqlite3.Source("unifist-sqlite3", os.path.join(self.directory, "unifist.db"))

        for model in MODELS:
            self.source.execute(self.source.define(model.thy().define()))

    def tearDown(self):

        self.source.connection.close()
        shutil.rmtree(self.directory, ignore_errors=True)

    def test_length(self):

        cursor = self.source.connection.cursor()

        for name in CAPPED:

            values = {"home": "u", "source": "s", "model": "m", name: "x" * 64}

            cursor.execute(
                "INSERT INTO `sequence` (`home`, `source`, `model`) VALUES (?, ?, ?)",
                (values["home"], values["source"], values["model"])
            )

            values[name] = "x" * 65

            self.assertRaises(
                sqlite3.IntegrityError,
                cursor.execute,
                "INSERT INTO `sequence` (`home`, `source`, `model`) VALUES (?, ?, ?)",
                (values["home"], values["source"], values["model"])
            )

        cursor.close()
