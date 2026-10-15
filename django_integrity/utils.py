from django.db.migrations.loader import MigrationLoader
from django.db import models


def field_names_to_column_names(modelClass, field_names):
    assert issubclass(modelClass, models.Model)
    return [modelClass._meta.get_field(fn).column for fn in field_names]


def get_app_current_migration_dependencies(app_label):
    loader = MigrationLoader(None, ignore_no_migrations=True)
    leaf_nodes = loader.graph.leaf_nodes(app_label)
    return [(app_label, leaf_node[1]) for leaf_node in leaf_nodes]


def getMigrationSQL(connection, migration):
    executor = MigrationExecutor(connection)
    state = executor.loader.project_state()
    with connection.schema_editor(collect_sql=True) as schema_editor:
        migration.apply(state.clone(), schema_editor)
        return list(schema_editor.collected_sql)
