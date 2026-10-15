"""django_integrity.base.DjangoModelIntegrityDiffExecutor_SchemeEditor: filling
and dropping lost integrity by running the SQL."""

from django_integrity import DjangoModelIntegrityDiff, DjangoModelIntegrityDiffExecutor_SchemeEditor as SchemeEditor

from testapp_django_integrity.models import Account, AuditLog
from testapp_django_integrity.tests import drift
from testapp_django_integrity.tests.base import AccountTestCase, IntegrityTestCase
from testapp_django_integrity.tests.test_diff import ACCOUNT_WITHOUT_CONSTRAINT, ACCOUNT_WITHOUT_EMAIL_UNIQUE, summary

ACCOUNT_TABLE = Account._meta.db_table
AUDITLOG_TABLE = AuditLog._meta.db_table
USERNAME_INDEX = 'testapp_django_integrity_account_username_e7516b85'
UNIQUE_TOGETHER_INDEX = 'testapp_django_integrity_account_first_name_last_name_b4cb0f26_uniq'
EMAIL_UNIQUE = 'testapp_django_integrity_account_email_c83b27ad_uniq'


def executor(modelClass, dry_run=False):
    return SchemeEditor(modelClass, dry_run)


def lost_of(modelClass):
    return summary(DjangoModelIntegrityDiff(modelClass).lost_integrity_in_db())



class FillLostDryRunTests(AccountTestCase):
    def test_an_in_sync_database_collects_no_sql(self):
        self.assertEqual(executor(Account, dry_run=True).fill_lost(), [])

    def test_a_dropped_field_index_collects_one_create_index(self):
        self.drop_index(ACCOUNT_TABLE, columns=('username',), unique=False)
        statements = executor(Account, dry_run=True).fill_lost()
        self.assertEqual(len(statements), 1)
        self.assertIn('CREATE INDEX', statements[0])
        self.assertIn(USERNAME_INDEX, statements[0])

    def test_a_dropped_named_index_is_recreated_with_its_declared_name(self):
        self.drop_index(ACCOUNT_TABLE, name='account_last_balance_idx')
        statements = executor(Account, dry_run=True).fill_lost()
        self.assertEqual(len(statements), 1)
        self.assertIn('account_last_balance_idx', statements[0])

    def test_a_dropped_unique_together_is_recreated(self):
        self.drop_index(ACCOUNT_TABLE, columns=('first_name', 'last_name'), unique=True)
        statements = executor(Account, dry_run=True).fill_lost()
        self.assertEqual(len(statements), 1)
        self.assertIn('CREATE UNIQUE INDEX', statements[0])
        self.assertIn(UNIQUE_TOGETHER_INDEX, statements[0])

    def test_a_removed_named_constraint_is_recreated(self):
        self.rebuild_table(ACCOUNT_TABLE, ACCOUNT_WITHOUT_CONSTRAINT)
        statements = executor(Account, dry_run=True).fill_lost()
        self.assertEqual(len(statements), 1)
        self.assertIn('account_first_email_uniq', statements[0])

    def test_an_inline_unique_column_is_recreated_as_a_named_constraint(self):
        self.rebuild_table(ACCOUNT_TABLE, ACCOUNT_WITHOUT_EMAIL_UNIQUE)
        statements = executor(Account, dry_run=True).fill_lost()
        self.assertEqual(len(statements), 1)
        self.assertIn('UNIQUE', statements[0])
        self.assertIn(EMAIL_UNIQUE, statements[0])

    def test_a_dry_run_changes_nothing(self):
        self.drop_index(ACCOUNT_TABLE, columns=('username',), unique=False)
        before = self.index_names(ACCOUNT_TABLE)
        executor(Account, dry_run=True).fill_lost()
        self.assertEqual(self.index_names(ACCOUNT_TABLE), before)


class FillLostTests(AccountTestCase):
    def test_a_dropped_field_index_is_recreated_with_the_same_name(self):
        self.drop_index(ACCOUNT_TABLE, columns=('username',), unique=False)
        executor(Account).fill_lost()
        self.assertIn(USERNAME_INDEX, self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['field_index'], [])

    def test_a_dropped_named_index_is_recreated_with_the_same_name(self):
        self.drop_index(ACCOUNT_TABLE, name='account_last_balance_idx')
        executor(Account).fill_lost()
        self.assertIn('account_last_balance_idx', self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['model_meta_indexes'], [])

    def test_a_dropped_unique_together_is_recreated(self):
        self.drop_index(ACCOUNT_TABLE, columns=('first_name', 'last_name'), unique=True)
        executor(Account).fill_lost()
        self.assertIn(UNIQUE_TOGETHER_INDEX, self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['model_unique_together_tuples'], [])

    def test_an_removed_named_constraint_is_recreated(self):
        self.rebuild_table(ACCOUNT_TABLE, ACCOUNT_WITHOUT_CONSTRAINT)
        executor(Account).fill_lost()
        self.assertIn('account_first_email_uniq', DjangoModelIntegrityDiff(Account).db_constraints)
        self.assertEqual(lost_of(Account)['model_meta_constraints'], [])

    def test_filling_an_in_sync_database_changes_nothing(self):
        before = self.index_names(ACCOUNT_TABLE)
        executor(Account).fill_lost()
        self.assertEqual(self.index_names(ACCOUNT_TABLE), before)

    def test_a_real_run_returns_nothing(self):
        self.drop_index(ACCOUNT_TABLE, columns=('username',), unique=False)
        self.assertIsNone(executor(Account).fill_lost())

    def test_the_rows_survive_a_fill(self):
        Account.objects.create(email='a@example.com', username='ann', both='x', first_name='Ann', last_name='A', legacy='')
        self.drop_index(ACCOUNT_TABLE, columns=('username',), unique=False)
        executor(Account).fill_lost()
        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(Account.objects.get().email, 'a@example.com')


class DropForDryRunTests(AccountTestCase):
    def test_dropping_a_field_index_collects_a_drop_index(self):
        statements = executor(Account, dry_run=True).drop_for('username')
        self.assertEqual(statements, ['DROP INDEX "%s";' % USERNAME_INDEX])

    def test_dropping_a_named_index_collects_a_drop_index(self):
        statements = executor(Account, dry_run=True).drop_for('last_name')
        self.assertEqual(statements[0], 'DROP INDEX "account_last_balance_idx";')

    def test_dropping_a_unique_together_rebuilds_the_table(self):
        statements = executor(Account, dry_run=True).drop_for('first_name')
        self.assertTrue(any('CREATE TABLE "new__' in statement for statement in statements))
        self.assertTrue(any('CREATE UNIQUE INDEX "%s"' % UNIQUE_TOGETHER_INDEX in statement for statement in statements))

    def test_dropping_an_inline_unique_column_rebuilds_the_table(self):
        statements = executor(Account, dry_run=True).drop_for('email')
        self.assertTrue(any('CREATE TABLE "new__' in statement for statement in statements))

    def test_dropping_for_a_column_with_nothing_declared_collects_nothing(self):
        self.assertEqual(executor(Account, dry_run=True).drop_for('legacy'), [])

    def test_a_dry_run_changes_nothing(self):
        before = self.index_names(ACCOUNT_TABLE)
        executor(Account, dry_run=True).drop_for('username')
        self.assertEqual(self.index_names(ACCOUNT_TABLE), before)


class DropForTests(AccountTestCase):
    def test_a_field_index_is_dropped(self):
        executor(Account).drop_for('username')
        self.assertNotIn(USERNAME_INDEX, self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['field_index'], ['username'])

    def test_a_named_index_is_dropped(self):
        executor(Account).drop_for('last_name')
        self.assertNotIn('account_last_balance_idx', self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['model_meta_indexes'], ['account_last_balance_idx'])

    def test_a_unique_together_is_dropped(self):
        executor(Account).drop_for('first_name')
        self.assertNotIn(UNIQUE_TOGETHER_INDEX, self.index_names(ACCOUNT_TABLE))
        self.assertEqual(lost_of(Account)['model_unique_together_tuples'], [('first_name', 'last_name')])

    def test_the_other_indexes_survive_a_drop(self):
        executor(Account).drop_for('username')
        self.assertIn('account_last_balance_idx', self.index_names(ACCOUNT_TABLE))
        self.assertIn(UNIQUE_TOGETHER_INDEX, self.index_names(ACCOUNT_TABLE))

    def test_dropping_for_a_column_with_nothing_declared_changes_nothing(self):
        before = self.index_names(ACCOUNT_TABLE)
        self.assertIsNone(executor(Account).drop_for('legacy'))
        self.assertEqual(self.index_names(ACCOUNT_TABLE), before)

    def test_a_dropped_field_can_be_filled_again(self):
        executor(Account).drop_for('username')
        executor(Account).fill_lost()
        self.assertEqual(lost_of(Account)['field_index'], [])


class FillAndDropRoundTripTests(AccountTestCase):
    def test_drop_then_fill_restores_the_original_scheme(self):
        before = sorted(self.db_constraints(ACCOUNT_TABLE))
        executor(Account).drop_for('last_name')
        executor(Account).drop_for('username')
        executor(Account).fill_lost()
        self.assertEqual(sorted(self.db_constraints(ACCOUNT_TABLE)), before)

