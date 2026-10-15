import django
from django.db import connection, models
from .utils import field_names_to_column_names


class DjangoModelIntegrity(object):

	def __init__(self):
		self.model_meta_indexes = []
		self.model_meta_constraints = []
		self.model_unique_together_tuples = []
		self.model_index_together_tuples = []
		self.field_unique = []
		self.field_index = []

	def add_model_meta_index(self, model_meta_index):
		assert isinstance(model_meta_index, models.Index)
		self.model_meta_indexes.append(model_meta_index)

	def add_model_meta_constraint(self, model_meta_constraint):
		assert isinstance(model_meta_constraint, models.BaseConstraint)
		self.model_meta_constraints.append(model_meta_constraint)

	def add_model_unique_together(self, model_unique_together):
		self.model_unique_together_tuples.append(model_unique_together)

	def add_model_index_together(self, model_index_together):
		self.model_index_together_tuples.append(model_index_together)

	def add_field_unique(self, field):
		assert field.unique and not field.primary_key
		self.field_unique.append(field)

	def add_field_index(self, field):
		assert field.db_index and not field.unique and not field.primary_key
		self.field_index.append(field)

	def get_indexes_list(self, modelClass):
		assert issubclass(modelClass, models.Model)
		table_name = modelClass._meta.db_table
		part_index = []
		with connection.schema_editor() as schema_editor:
			for field_names in self.__get_indexes_tuples_list__():
				column_names = list(field_names_to_column_names(modelClass, field_names))
				index_name = schema_editor._create_index_name(table_name, column_names)
				idx_obj = models.Index(fields=field_names, name=index_name)
				part_index.append(idx_obj)
		return part_index + self.__get_model_indexes_list__()

	def __get_model_indexes_list__(self):
		return list(self.model_meta_indexes)

	def __get_model_constraints_list__(self):
		return list(self.model_meta_constraints)

	def __get_indexes_tuples_list__(self):
		return list([(field.name, ) for field in self.field_index]) + list(self.model_index_together_tuples)

	def __get_unique_tuples_list__(self):
		return list([(field.name, ) for field in self.field_unique]) + list(self.model_unique_together_tuples)

	def get_constraints_list(self, modelClass):
		assert issubclass(modelClass, models.Model)
		table_name = modelClass._meta.db_table
		part_unique = []
		with connection.schema_editor() as schema_editor:
			for field_names in self.__get_unique_tuples_list__():
				column_names = list(field_names_to_column_names(modelClass, field_names))
				constraint_name = str(schema_editor._unique_constraint_name(table_name, column_names, quote=False))
				cst_obj = models.UniqueConstraint(fields=field_names, name=constraint_name)
				part_unique.append(cst_obj)
		return part_unique + self.__get_model_constraints_list__()


class ConstraintField(object):

	@classmethod
	def is_field_referred_in_constraint_Q(cls, Q_node, field_name):
		assert isinstance(Q_node, models.Q)
		for child in Q_node.children:
			if isinstance(child, models.Q):
				if cls.is_field_referred_in_constraint_Q(child, field_name):
					return True
			elif isinstance(child, tuple) and len(child) == 2:
				lookup_key, value = child
				target_field = lookup_key.split('__')[0]
				if target_field == field_name:
					return True
				if isinstance(value, models.F) and value.name == field_name:
					return True
		return False

	@classmethod
	def is_field_referred_in_constrain(cls, constraint, field_name):
		assert isinstance(constraint, models.BaseConstraint)
		if isinstance(constraint, models.CheckConstraint):
			node = None
			try:
				node = constraint.condition
			except AttributeError:
				node = constraint.check
			return node and cls.is_field_referred_in_constraint_Q(node, field_name)
		elif isinstance(constraint, models.UniqueConstraint):

			fields = []
			try:
				fields = list(constraint.fields)
			except AttributeError:
				fields = []
			if not fields:
				fields = []

			include = []
			try:
				include = list(constraint.include)
			except AttributeError:
				include = []
			if not fields:
				include = []

			node = None
			try:
				node = constraint.condition
			except AttributeError:
				pass

			return field_name in fields or field_name in include or node and cls.is_field_referred_in_constraint_Q(node, field_name)


class DjangoModelIntegrityDiff(object):

	def __init__(self, modelClass):
		assert issubclass(modelClass, models.Model)
		self.modelClass = modelClass

	@property
	def table_name(self):
		return self.modelClass._meta.db_table

	@property
	def db_constraints(self):
		with connection.cursor() as cursor:
			return connection.introspection.get_constraints(cursor, self.table_name)

	def field_has_db_unique(self, field, db_constraints):
		column_name = field.column
		col_tuple = (column_name,)
		return any(details['unique'] and col_tuple == tuple(details['columns']) for details in db_constraints.values())

	def field_has_db_index(self, field, db_constraints):
		column_name = field.column
		col_tuple = (column_name,)
		return any(not details['unique'] and col_tuple == tuple(details['columns']) for details in db_constraints.values())

	def has_unique_together_in_db(self, ut_tuple, db_constraints):
		return any(details['unique'] and tuple(field_names_to_column_names(self.modelClass, ut_tuple)) == tuple(details['columns']) for details in db_constraints.values())

	def has_index_together_in_db(self, it_tuple, db_constraints):
		return any(not details['unique'] and tuple(field_names_to_column_names(self.modelClass, it_tuple)) == tuple(details['columns']) for details in db_constraints.values())

	def intersection_by_field(self, field_name):
		"return indexes and constraints referring particular field both in model definition and real database"
		field = self.modelClass._meta.get_field(field_name)

		integrity = DjangoModelIntegrity()
		db_constraints = dict(self.db_constraints)

		for idx in self.modelClass._meta.indexes:
			if field_name in idx.fields and idx.name in db_constraints:
				integrity.add_model_meta_index(idx)
				del db_constraints[idx.name]
		for cst in self.modelClass._meta.constraints:
			if ConstraintField.is_field_referred_in_constrain(cst, field_name) and cst.name in db_constraints:
				integrity.add_model_meta_constraint(cst)
				del db_constraints[cst.name]

		for ut in self.modelClass._meta.unique_together:
			if field_name in ut and self.has_unique_together_in_db(ut, db_constraints):
				integrity.add_model_unique_together(ut)

		if django.VERSION < (5, 1):
			for it in self.modelClass._meta.index_together:
				if field_name in it and self.has_index_together_in_db(it, db_constraints):
					integrity.add_model_index_together(it)

		if field.unique and not field.primary_key and self.field_has_db_unique(field, db_constraints):
			integrity.add_field_unique(field)
		if field.db_index and not field.unique and not field.primary_key and self.field_has_db_index(field, db_constraints):
			integrity.add_field_index(field)

		return integrity

	def lost_integrity_in_db(self):
		"return all indexes and constraints exist in model definition but not found in real database"
		integrity = DjangoModelIntegrity()
		db_constraints = dict(self.db_constraints)

		for idx in self.modelClass._meta.indexes:
			if idx.name in db_constraints:
				del db_constraints[idx.name]
			else:
				integrity.add_model_meta_index(idx)
		for cst in self.modelClass._meta.constraints:
			if cst.name in db_constraints:
				del db_constraints[cst.name]
			else:
				integrity.add_model_meta_constraint(cst)

		for ut in self.modelClass._meta.unique_together:
			if not self.has_unique_together_in_db(ut, db_constraints):
				integrity.add_model_unique_together(ut)

		if django.VERSION < (5, 1):
			for it in self.modelClass._meta.index_together:
				if not self.has_index_together_in_db(it, db_constraints):
					integrity.add_model_index_together(it)

		for field in self.modelClass._meta.local_fields:
			if field.unique and not field.primary_key and not self.field_has_db_unique(field, db_constraints):
				integrity.add_field_unique(field)
			if field.db_index and not field.unique and not field.primary_key and not self.field_has_db_index(field, db_constraints):
				integrity.add_field_index(field)

		return integrity


class DjangoModelIntegrityDiffExecutor_SchemeEditor(object):
	'dry run return sql.real run execute sql'

	def __init__(self, modelClass, dry_run=False):
		self.modelClass = modelClass
		self.diff = DjangoModelIntegrityDiff(modelClass)
		self.dry_run = bool(dry_run)

	def drop_for(self, field_name):
		integrity = self.diff.intersection_by_field(field_name)
		indexes = list(integrity.get_indexes_list(self.modelClass))
		constraints = list(integrity.get_constraints_list(self.modelClass))
		with connection.schema_editor(collect_sql=self.dry_run) as schema_editor:
			for index in indexes:
				schema_editor.remove_index(self.modelClass, index)
			for cst in constraints:
				schema_editor.remove_constraint(self.modelClass, cst)
			if self.dry_run:
				return list(schema_editor.collected_sql)

	def fill_lost(self):
		integrity = self.diff.lost_integrity_in_db()
		indexes = list(integrity.get_indexes_list(self.modelClass))
		constraints = list(integrity.get_constraints_list(self.modelClass))
		with connection.schema_editor(collect_sql=self.dry_run) as schema_editor:
			for index in indexes:
				schema_editor.add_index(self.modelClass, index)
			for cst in constraints:
				schema_editor.add_constraint(self.modelClass, cst)
			if self.dry_run:
				return list(schema_editor.collected_sql)


from django.db.migrations import operations
from .utils import get_app_current_migration_dependencies, getMigrationSQL

class DjangoModelIntegrityDiffExecutor_Migration(object):
	'dry run return sql. real run write migration file'

	def __init__(self, modelClass, dry_run):
		self.modelClass = modelClass
		self.diff = DjangoModelIntegrityDiff(modelClass)
		self.dry_run = bool(dry_run)

	def drop_for(self, field_name, app_label=None):
		if not app_label:
			app_label = self.modelClass._meta.app_label
		integrity = self.diff.intersection_by_field(field_name)
		indexes = list(integrity.get_indexes_list(self.modelClass))
		constraints = list(integrity.get_constraints_list(self.modelClass))
		operations = list([operations.RemoveIndex(self.modelClass, idx) for idx in indexes]) + list([operations.RemoveConstraint(self.modelClass, cst) for cst in constraints])

		migration_name = f"drop_integrity_for_{self.modelClass.name.lower()}_{field_name}"
		migration = Migration(migration_name, app_label)
		migration.operations = operations
		migration.dependencies = get_app_current_migration_dependencies(app_label)

		if self.dry_run:
			return getMigrationSQL(connection, migration)
		else:
			with open(writer.path, 'w', encoding='utf-8') as f:
				f.write(writer.as_string())

	def fill_lost(self, app_label=None):
		if not app_label:
			app_label = self.modelClass._meta.app_label
		integrity = self.diff.lost_integrity_in_db()
		indexes = list(integrity.get_indexes_list(self.modelClass))
		constraints = list(integrity.get_constraints_list(self.modelClass))
		operations = list([operations.AddIndex(self.modelClass, idx) for idx in indexes]) + list([operations.AddConstraint(self.modelClass, cst) for cst in constraints])

		migration_name = f"fill_lost_integrity_for_{self.modelClass.name.lower()}"
		migration = Migration(migration_name, app_label)
		migration.operations = operations
		migration.dependencies = get_app_current_migration_dependencies(app_label)

		if self.dry_run:
			return getMigrationSQL(connection, migration)
		else:
			with open(writer.path, 'w', encoding='utf-8') as f:
				f.write(writer.as_string())


