"""Shared base classes for the django_integrity tests."""

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from testapp_django_integrity import models as testapp_models
from testapp_django_integrity.tests import drift

#: Every table of the test app, parents first. ``tearDown`` drops all of them, not
#: only the ones a test declared, because a table that survived a test would be
#: left pointing at a parent table the test dropped, and the flush that
#: ``TransactionTestCase`` runs afterwards would fail on that dangling reference.
ALL_MODELS = (
    testapp_models.Model1,
)


class ConnectionTestCase(SimpleTestCase):
    """A ``SimpleTestCase`` that may still touch the connection.

    The library opens ``connection.schema_editor()`` even when it only needs an
    index name, and SQLite's schema editor issues a statement to disable foreign
    key checks on entry. That is a query, so it needs the database declared even
    though these tests never create a table.
    """

    databases = ['default']


class IntegrityTestCase(TransactionTestCase):
    """A test case that owns the tables of the models it declares.

    ``models`` lists the models the test works with, parents first. ``setUp``
    builds their tables from the model definitions, so every test starts with a
    database that is in sync with the models and the test is free to damage it.

    ``TransactionTestCase`` is required because the SQLite schema editor refuses
    to run inside the transaction that ``TestCase`` opens: it has to disable
    foreign key checks first, and SQLite cannot do that mid transaction.
    """

    models = ()

    def setUp(self):
        super().setUp()
        self.drop_all_tables()
        self.create_tables()

    def tearDown(self):
        self.drop_all_tables()
        super().tearDown()

    def create_tables(self):
        """Create the tables of ``self.models`` from the model definitions."""
        with connection.schema_editor() as schema_editor:
            for model in self.models:
                schema_editor.create_model(model)

    def drop_all_tables(self):
        """Drop every table of the test app, children before parents.

        A test only creates the tables it declares, so the ones it did not are
        simply not there; the ``IF EXISTS`` keeps that from being an error.
        """
        with connection.cursor() as cursor:
            for model in reversed(ALL_MODELS):
                cursor.execute('DROP TABLE IF EXISTS "%s"' % model._meta.db_table)

    # -- helpers that make the database drift --------------------------------

    def drop_index(self, table, columns=None, name=None, unique=None):
        return drift.drop_index(table, columns=columns, name=name, unique=unique)

    def drop_table(self, table):
        return drift.drop_table(table)

    def create_index(self, name, table, columns, unique=False):
        return drift.create_index(name, table, columns, unique=unique)

    def rebuild_table(self, table, ddl, keep_indexes=None):
        return drift.rebuild_table(table, ddl, keep_indexes=keep_indexes)

    def index_names(self, table, columns=None, unique=None):
        return drift.index_names(table, columns=columns, unique=unique)

    def index_ddl(self, table):
        return drift.index_ddl(table)

    def db_constraints(self, table):
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

