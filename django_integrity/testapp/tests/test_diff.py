import unittest

import django
from django.db import models
from django.test import SimpleTestCase

from django_integrity import DjangoModelIntegrityDiff
from django_integrity.base import ConstraintField
from testapp_django_integrity.models import Model1, check_constraint, CHECK_CONDITION_KWARG
from testapp_django_integrity.tests import drift
from testapp_django_integrity.tests.base import IntegrityTestCase


def summary(integrity):
    """The collected integrity as plain comparable data."""
    return {
        'model_meta_indexes': [index.name for index in integrity.model_meta_indexes],
        'model_meta_constraints': [constraint.name for constraint in integrity.model_meta_constraints],
        'model_unique_together_tuples': [tuple(item) for item in integrity.model_unique_together_tuples],
        'model_index_together_tuples': [tuple(item) for item in integrity.model_index_together_tuples],
        'field_unique': [field.name for field in integrity.field_unique],
        'field_index': [field.name for field in integrity.field_index],
    }


EMPTY = {
    'model_meta_indexes': [],
    'model_meta_constraints': [],
    'model_unique_together_tuples': [],
    'model_index_together_tuples': [],
    'field_unique': [],
    'field_index': [],
}

#: The model1 table without its named UNIQUE table level constraint. SQLite
#: cannot drop an inline UNIQUE, but a named constraint goes with a table rebuild.
MODEL1_WITHOUT_CONSTRAINT = drift.model1_ddl(without_constraint=('m1_uf3_uf4_uniq',))

#: The model1 table without the inline UNIQUE of the column of ``uf1``.
MODEL1_WITHOUT_UF1_UNIQUE = drift.model1_ddl(without_unique=('gerd',))

#: The model1 table without any named constraint.
MODEL1_WITHOUT_ANY_CONSTRAINT = drift.model1_ddl(
    without_constraint=('m1_uf3_uf4_uniq', 'cq_f1', 'cq_2')
)


class DbConstraintsTests(IntegrityTestCase):

    models = (Model1,)
    table = Model1._meta.db_table

    def setUp(self):
        super().setUp()
        self.diff = DjangoModelIntegrityDiff(Model1)
        self.db_constraints = self.diff.db_constraints

    def test_every_declared_named_declaration_is_reported(self):
        for name in ('m1_uf3_uf4_uniq', 'cq_f1', 'cq_2',
                     'm1_f1_if1_idx', 'm1_if1_f1_idx', 'm1_if3_uf4_idx', 'm1_uf2_partial_idx'):
            self.assertIn(name, self.db_constraints)

    def test_the_named_unique_constraint_reports_its_columns(self):
        details = self.db_constraints['m1_uf3_uf4_uniq']
        self.assertEqual(details['columns'], ['jy', 'vh'])
        self.assertTrue(details['unique'])

    def test_a_declared_index_reports_its_columns_and_order(self):
        details = self.db_constraints['m1_f1_if1_idx']
        self.assertEqual(details['columns'], ['aaaa', 'tu'])
        self.assertEqual(details['orders'], ['ASC', 'DESC'])

    def test_an_inline_unique_column_is_reported_as_an_unnamed_constraint(self):
        unnamed = [name for name in self.db_constraints if name.startswith('__unnamed')]
        self.assertEqual(len(unnamed), 6)
        self.assertEqual(
            sorted(tuple(self.db_constraints[name]['columns']) for name in unnamed),
            [('dfb',), ('gerd',), ('hty',), ('jhj',), ('jy',), ('qsdf',)],
        )

    def test_a_unique_field_has_a_unique_constraint(self):
        self.assertTrue(self.diff.field_has_db_unique(Model1._meta.get_field('uf1'), self.diff.db_constraints))

    def test_an_indexed_field_is_not_unique(self):
        self.assertFalse(self.diff.field_has_db_unique(Model1._meta.get_field('if1'), self.diff.db_constraints))

    def test_a_plain_field_is_not_unique(self):
        self.assertFalse(self.diff.field_has_db_unique(Model1._meta.get_field('if2'), self.diff.db_constraints))

    def test_a_field_is_compared_under_its_db_column_not_its_field_name(self):
        # uf1 is the field, gerd is the column, so only the column can be found.
        field = Model1._meta.get_field('uf1')
        self.assertEqual(field.name, 'uf1')
        self.assertEqual(field.column, 'gerd')
        self.assertTrue(self.diff.field_has_db_unique(field, self.diff.db_constraints))

    def test_a_unique_char_field_is_unique(self):
        self.assertTrue(self.diff.field_has_db_unique(Model1._meta.get_field('uf3'), self.diff.db_constraints))

    def test_a_unique_field_with_an_index_too_is_unique(self):
        self.assertTrue(self.diff.field_has_db_unique(Model1._meta.get_field('iuf1'), self.diff.db_constraints))

    def test_the_primary_key_is_not_reported_as_a_unique_field(self):
        self.assertFalse(self.diff.field_has_db_unique(Model1._meta.get_field('id'), self.diff.db_constraints))

    def test_an_indexed_field_has_an_index(self):
        self.assertTrue(self.diff.field_has_db_index(Model1._meta.get_field('if1'), self.diff.db_constraints))

    def test_a_unique_field_is_not_counted_as_a_plain_index(self):
        self.assertFalse(self.diff.field_has_db_index(Model1._meta.get_field('uf1'), self.diff.db_constraints))

    def test_a_plain_field_has_no_index(self):
        self.assertFalse(self.diff.field_has_db_index(Model1._meta.get_field('if2'), self.diff.db_constraints))

    def test_a_unique_together_that_exists_is_found(self):
        self.assertTrue(self.diff.has_unique_together_in_db(('uf1', 'f1'), self.diff.db_constraints))

    def test_a_unique_together_that_does_not_exist_is_not_found(self):
        self.assertFalse(self.diff.has_unique_together_in_db(('uf1', 'uf2'), self.diff.db_constraints))

    def test_the_column_order_matters(self):
        self.assertFalse(self.diff.has_unique_together_in_db(('f1', 'uf1'), self.diff.db_constraints))


class IntersectionByFieldTests(IntegrityTestCase):

    models = (Model1,)
    table = Model1._meta.db_table

    def setUp(self):
        super().setUp()
        self.diff = DjangoModelIntegrityDiff(Model1)
        self.db_constraints = self.diff.db_constraints

    def collect(self, field_name):
        return summary(self.diff.intersection_by_field(field_name))

    def test_a_field_that_declares_nothing_collects_nothing(self):
        self.assertEqual(self.collect('if2'), EMPTY)

    def test_a_unique_field_collects_its_unique_constraint(self):
        self.assertEqual(self.collect('uf1')['field_unique'], ['uf1'])

    def test_an_indexed_field_collects_its_index(self):
        self.assertEqual(self.collect('if1')['field_index'], ['if1'])

    def test_a_named_index_is_collected_for_the_first_column_it_covers(self):
        # m1_if3_uf4_idx is declared on if3, so it belongs to if3 and not to uf4.
        self.assertEqual(self.collect('if3')['model_meta_indexes'], ['m1_if3_uf4_idx'])
        self.assertEqual(self.collect('uf4')['model_meta_indexes'], [])

    def test_a_partial_index_is_collected_like_any_other_named_index(self):
        self.assertEqual(self.collect('uf2')['model_meta_indexes'], ['m1_uf2_partial_idx'])

    def test_a_named_constraint_is_collected_for_every_column_it_covers(self):
        self.assertEqual(self.collect('uf3')['model_meta_constraints'], ['m1_uf3_uf4_uniq'])
        self.assertEqual(self.collect('uf4')['model_meta_constraints'], ['m1_uf3_uf4_uniq'])

    def test_a_unique_together_is_collected_for_every_column_it_covers(self):
        self.assertEqual(self.collect('uf1')['model_unique_together_tuples'], [('uf1', 'f1')])
        self.assertEqual(self.collect('f1')['model_unique_together_tuples'], [('uf1', 'f1'), ('if1', 'f1')])

    def test_everything_a_column_declares_is_collected_at_once(self):
        self.assertEqual(
            self.collect('if1'),
            dict(
                EMPTY,
                model_meta_indexes=['m1_if1_f1_idx'],
                model_unique_together_tuples=[('if1', 'f1')],
                field_index=['if1'],
            ),
        )

    def test_a_dropped_named_index_is_not_collected(self):
        self.drop_index(self.table, name='m1_if3_uf4_idx')
        self.assertEqual(self.collect('if3')['model_meta_indexes'], [])

    def test_a_removed_named_constraint_is_not_collected(self):
        self.rebuild_table(self.table, MODEL1_WITHOUT_CONSTRAINT)
        self.assertEqual(self.collect('uf3')['model_meta_constraints'], [])

    def test_a_dropped_field_index_is_not_collected(self):
        self.drop_index(self.table, columns=('tu',), unique=False)
        self.assertEqual(self.collect('if1')['field_index'], [])

    def test_a_column_of_two_named_indexes_reports_both(self):
        # f1 is the second column of m1_if1_f1_idx and the first column of
        # m1_f1_if1_idx, and both declare it.
        collected = self.collect('f1')
        self.assertEqual(collected['model_meta_indexes'], ['m1_f1_if1_idx', 'm1_if1_f1_idx'])

    def test_the_first_column_of_a_multi_column_index_also_reports_its_own_index(self):
        # if3 carries its own field index on top of m1_if3_uf4_idx.
        collected = self.collect('if3')
        self.assertEqual(collected['model_meta_indexes'], ['m1_if3_uf4_idx'])
        self.assertEqual(collected['field_index'], ['if3'])

    @unittest.skip('a check constraint is collected for every field its condition names')
    def test_a_check_constraint_has_no_columns_so_it_is_collected_for_nobody(self):
        self.assertEqual(self.collect('f1')['model_meta_constraints'], [])
        self.assertEqual(self.collect('uf1')['model_meta_constraints'], [])

    def test_a_check_constraint_is_still_reported_when_the_whole_table_is_asked_about(self):
        collected = summary(DjangoModelIntegrityDiff(Model1).lost_integrity_in_db())
        self.assertEqual(collected['model_meta_constraints'], [])
        self.assertIn('cq_f1', DjangoModelIntegrityDiff(Model1).db_constraints)
        self.assertIn('cq_2', DjangoModelIntegrityDiff(Model1).db_constraints)


class LostIntegrityInDbTests(IntegrityTestCase):

    models = (Model1,)
    table = Model1._meta.db_table

    def setUp(self):
        super().setUp()
        self.diff = DjangoModelIntegrityDiff(Model1)
        self.db_constraints = self.diff.db_constraints

    def lost(self):
        return summary(self.diff.lost_integrity_in_db())

    def test_an_in_sync_database_has_nothing_lost(self):
        self.assertEqual(self.lost(), EMPTY)

    def test_a_dropped_field_index_is_reported(self):
        self.drop_index(self.table, columns=('tu',), unique=False)
        self.assertEqual(self.lost()['field_index'], ['if1'])

    def test_a_dropped_named_index_is_reported_by_its_declared_name(self):
        self.drop_index(self.table, name='m1_f1_if1_idx')
        self.assertEqual(self.lost()['model_meta_indexes'], ['m1_f1_if1_idx'])

    def test_a_removed_named_constraint_is_reported_by_its_declared_name(self):
        self.rebuild_table(self.table, MODEL1_WITHOUT_CONSTRAINT)
        self.assertEqual(self.lost()['model_meta_constraints'], ['m1_uf3_uf4_uniq'])

    def test_an_inline_unique_column_that_is_gone_is_reported(self):
        self.rebuild_table(self.table, MODEL1_WITHOUT_UF1_UNIQUE)
        self.assertEqual(self.lost()['field_unique'], ['uf1'])

    def test_a_removed_unique_together_is_reported_as_a_tuple(self):
        self.drop_index(self.table, columns=('gerd', 'aaaa'), unique=True)
        self.assertEqual(self.lost()['model_unique_together_tuples'], [('uf1', 'f1')])

    def test_several_declarations_can_be_lost_at_once(self):
        self.drop_index(self.table, name='m1_f1_if1_idx')
        self.drop_index(self.table, columns=('tu',), unique=False)
        collected = self.lost()
        self.assertEqual(collected['model_meta_indexes'], ['m1_f1_if1_idx'])
        self.assertEqual(collected['field_index'], ['if1'])

    def test_a_lost_named_constraint_is_not_also_reported_as_a_lost_field(self):
        self.rebuild_table(self.table, MODEL1_WITHOUT_CONSTRAINT)
        collected = self.lost()
        self.assertEqual(collected['model_meta_constraints'], ['m1_uf3_uf4_uniq'])
        self.assertEqual(collected['field_unique'], [])

    def test_an_index_the_model_never_declared_is_not_reported(self):
        self.create_index('stranger_idx', self.table, ['dhff'])
        self.assertEqual(self.lost(), EMPTY)
        self.assertIn('stranger_idx', self.index_names(self.table))

    def test_a_missing_table_reports_everything_as_lost(self):
        self.drop_table(self.table)
        collected = self.lost()
        self.assertEqual(collected['field_unique'], ['uf1', 'uf3', 'iuf1', 'iuf3', 'iuf4', 'iuf6'])
        self.assertEqual(collected['field_index'], ['if1', 'if3', 'iuf2', 'iuf5'])
        self.assertEqual(
            collected['model_meta_indexes'],
            ['m1_f1_if1_idx', 'm1_if1_f1_idx', 'm1_if3_uf4_idx', 'm1_uf2_partial_idx'],
        )
        self.assertEqual(collected['model_unique_together_tuples'], [('uf1', 'f1'), ('if1', 'f1')])
        self.assertEqual(collected['model_meta_constraints'], ['m1_uf3_uf4_uniq', 'cq_f1', 'cq_2'])

    def test_a_dropped_index_is_the_only_thing_lost(self):
        # dgn carries nothing but its own field index, so dropping it is the only
        # damage the table can take.
        self.drop_index(self.table, columns=('dgn',), unique=False)
        collected = self.lost()
        self.assertEqual(collected['field_index'], ['iuf2'])
        self.assertEqual(collected['model_meta_indexes'], [])

    def test_a_dropped_check_constraint_is_reported(self):
        self.rebuild_table(self.table, MODEL1_WITHOUT_ANY_CONSTRAINT)
        collected = self.lost()
        self.assertEqual(collected['model_meta_constraints'], ['m1_uf3_uf4_uniq', 'cq_f1', 'cq_2'])


class ConstraintFieldTests(SimpleTestCase):
    """``ConstraintField``: which fields a constraint declaration refers to.

    The constraints here are built with the ``check_constraint`` helper rather
    than declared on a model, so that the keyword this Django version expects
    (``check`` before 4.1, ``condition`` from 4.1 on) is exercised the same way
    the library reads it back.
    """

    def refers(self, constraint, field_name):
        return ConstraintField.is_field_referred_in_constrain(constraint, field_name)

    def test_a_check_constraint_refers_to_the_field_it_names(self):
        constraint = check_constraint(models.Q(f1__gte=1), 'cq_f1')
        self.assertTrue(self.refers(constraint, 'f1'))

    def test_a_check_constraint_does_not_refer_to_an_unrelated_field(self):
        constraint = check_constraint(models.Q(f1__gte=1), 'cq_f1')
        self.assertFalse(self.refers(constraint, 'if1'))

    def test_a_check_constraint_refers_to_every_field_of_a_conjunction(self):
        constraint = check_constraint(models.Q(uf1__gte=1) & models.Q(iuf1__gte=1), 'cq_2')
        self.assertTrue(self.refers(constraint, 'uf1'))
        self.assertTrue(self.refers(constraint, 'iuf1'))
        self.assertFalse(self.refers(constraint, 'f1'))

    def test_a_check_constraint_refers_to_a_field_nested_in_a_disjunction(self):
        constraint = check_constraint(models.Q(f1__gte=1) | models.Q(if1__gte=0), 'cq_nested')
        self.assertTrue(self.refers(constraint, 'if1'))

    def test_a_check_constraint_refers_to_a_field_reached_through_a_related_lookup(self):
        # the lookup key is 'if1__gte', so the field is if1 and not 'if1__gte'.
        constraint = check_constraint(models.Q(**{'if1__gte': 1}), 'cq_lookup')
        self.assertTrue(self.refers(constraint, 'if1'))
        self.assertFalse(self.refers(constraint, 'if1__gte'))

    def test_a_check_constraint_refers_to_a_field_compared_with_an_f_expression(self):
        constraint = check_constraint(models.Q(f1__gte=models.F('if1')), 'cq_f')
        self.assertTrue(self.refers(constraint, 'if1'))

    def test_a_unique_constraint_refers_to_the_fields_it_covers(self):
        constraint = models.UniqueConstraint(fields=('uf3', 'uf4'), name='m1_uf3_uf4_uniq')
        self.assertTrue(self.refers(constraint, 'uf3'))
        self.assertTrue(self.refers(constraint, 'uf4'))
        self.assertFalse(self.refers(constraint, 'f1'))

    def test_a_unique_constraint_refers_to_a_field_of_its_condition(self):
        condition_kwarg = CHECK_CONDITION_KWARG
        constraint = models.UniqueConstraint(
            fields=('uf2',),
            name='m1_uf2_partial_uniq',
            **{condition_kwarg: models.Q(if3__gte=0)},
        )
        self.assertTrue(self.refers(constraint, 'if3'))
        self.assertTrue(self.refers(constraint, 'uf2'))
        self.assertFalse(self.refers(constraint, 'f1'))

    def test_a_non_constraint_is_rejected(self):
        # an Index is not a BaseConstraint, and the library asks for one.
        with self.assertRaises(AssertionError):
            self.refers(models.Index(fields=('f1', '-if1'), name='m1_f1_if1_idx'), 'f1')