"""django_integrity.utils: column names, migration dependencies, migration SQL."""

from django.db import connection
from django.db import migrations
from django.db.models import CharField, ForeignKey
from django.test import SimpleTestCase

from django_integrity.utils import (
    field_names_to_column_names,
    get_app_current_migration_dependencies,
    getMigrationSQL,
)

from testapp_django_integrity.models import Account, Article
from testapp_django_integrity.tests.base import ConnectionTestCase


class FieldNamesToColumnNamesTests(SimpleTestCase):
    def test_plain_fields_keep_their_own_column_names(self):
        self.assertEqual(
            field_names_to_column_names(Account, ['first_name', 'last_name']),
            ['first_name', 'last_name'],
        )

    def test_a_foreign_key_resolves_to_its_column(self):
        # Article.account is the field name, account_id is the column name, and
        # a diff that mixed the two up would never match anything.
        self.assertEqual(field_names_to_column_names(Article, ['account']), ['account_id'])

    def test_an_empty_field_list_gives_an_empty_column_list(self):
        self.assertEqual(field_names_to_column_names(Account, []), [])

    def test_a_non_model_class_is_rejected(self):
        with self.assertRaises(AssertionError):
            field_names_to_column_names(CharField, ['name'])

    def test_an_unknown_field_name_is_rejected(self):
        with self.assertRaises(Exception):
            field_names_to_column_names(Account, ['nonexistent'])


class AppCurrentMigrationDependenciesTests(SimpleTestCase):
    def test_an_app_without_migrations_has_no_leaf(self):
        # testapp_django_integrity ships no migrations directory, so there is
        # nothing for a generated migration to depend on.
        self.assertEqual(get_app_current_migration_dependencies('testapp_django_integrity'), [])

    def test_every_leaf_belongs_to_the_asked_app(self):
        for dependency in get_app_current_migration_dependencies('django.contrib.contenttypes'):
            self.assertEqual(dependency[0], 'django.contrib.contenttypes')

    def test_an_unknown_app_label_gives_no_dependency(self):
        self.assertEqual(get_app_current_migration_dependencies('not_an_installed_app'), [])


class GetMigrationSQLTests(ConnectionTestCase):
    def make_migration(self, *operations):
        migration = migrations.Migration('test_migration', 'testapp_django_integrity')
        migration.operations = list(operations)
        return migration

    def test_an_add_index_migration_collects_create_index_sql(self):
        index = Account._meta.indexes[0]
        migration = self.make_migration(migrations.AddIndex('Account', index))
        statements = getMigrationSQL(connection, migration)
        self.assertEqual(len(statements), 1)
        self.assertIn('CREATE INDEX', statements[0])
        self.assertIn(index.name, statements[0])

    def test_a_remove_index_migration_collects_drop_index_sql(self):
        index = Account._meta.indexes[0]
        migration = self.make_migration(migrations.RemoveIndex('Account', index.name))
        statements = getMigrationSQL(connection, migration)
        self.assertEqual(len(statements), 1)
        self.assertIn('DROP INDEX', statements[0])
        self.assertIn(index.name, statements[0])

    def test_a_migration_without_operations_collects_nothing(self):
        self.assertEqual(getMigrationSQL(connection, self.make_migration()), [])

    def test_the_returned_statements_are_in_order(self):
        indexes = Account._meta.indexes
        migration = self.make_migration(
            migrations.AddIndex('Account', indexes[0]),
            migrations.AddIndex('Account', indexes[1]),
        )
        statements = getMigrationSQL(connection, migration)
        self.assertEqual(len(statements), 2)
        self.assertIn(indexes[0].name, statements[0])
        self.assertIn(indexes[1].name, statements[1])

