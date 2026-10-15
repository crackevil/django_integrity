"""Helpers that make the SQLite database drift inside a test.

``IntegrityTestCase.setUp`` builds the tables of its models from the model
definitions, so a test starts with a database that is in sync. These helpers
then damage it the way a real database drifts (an index dropped by hand, a
migration that was never applied, a constraint that was renamed), because
removing an index is the only drift the library is about.
"""

from django.db import connections

#: The columns of testapp_django_integrity_model1 in DDL form. Identifiers are
#: quoted the way Django quotes them, which is not cosmetic: SQLite's
#: get_constraints() parses the stored CREATE TABLE text, and hand written
#: unquoted DDL is parsed as garbage (``UNIQUE (gerd)`` is reported as a
#: constraint on a column called ``UNIQUE``).
MODEL1_COLUMNS = [
    ('id', 'integer NOT NULL PRIMARY KEY AUTOINCREMENT'),
    ('aaaa', 'integer NOT NULL'),
    ('gerd', 'integer NOT NULL'),
    ('dhff', 'integer NOT NULL'),
    ('jy', 'varchar(254) NOT NULL'),
    ('vh', 'varchar(254) NOT NULL'),
    ('tu', 'integer NOT NULL'),
    ('few', 'integer NOT NULL'),
    ('fn', 'varchar(254) NOT NULL'),
    ('uyk', 'varchar(254) NOT NULL'),
    ('dfb', 'integer NOT NULL'),
    ('dgn', 'integer NOT NULL'),
    ('qsdf', 'integer NOT NULL'),
    ('jhj', 'varchar(254) NOT NULL'),
    ('cb', 'varchar(254) NOT NULL'),
    ('hty', 'varchar(254) NOT NULL'),
]

#: The columns Django made unique with an inline UNIQUE constraint, in table order.
MODEL1_UNIQUE_COLUMNS = ('gerd', 'jy', 'dfb', 'qsdf', 'jhj', 'hty')

#: The named table level constraints Django created for the model1 table.
MODEL1_CONSTRAINTS = {
    'm1_uf3_uf4_uniq': 'CONSTRAINT "m1_uf3_uf4_uniq" UNIQUE ("jy", "vh")',
    'cq_f1': 'CONSTRAINT "cq_f1" CHECK ("aaaa" >= 1)',
    'cq_2': 'CONSTRAINT "cq_2" CHECK (("gerd" >= 1 AND "dfb" >= 1))',
}


def index_ddl(table, using='default'):
    """The CREATE INDEX statements of ``table``, keyed by index name."""
    connection_ = connections[using]
    with connection_.cursor() as cursor:
        cursor.execute(
            'SELECT name, sql FROM sqlite_master WHERE type = \'index\' AND tbl_name = %s AND sql IS NOT NULL',
            [table],
        )
        return {name: sql for name, sql in cursor.fetchall()}


def index_names(table, columns=None, unique=None, using='default'):
    """The names of the indexes of ``table``, optionally filtered.

    ``columns`` is matched as an ordered tuple, ``unique`` as the ``unique`` flag
    of the index. This is how the generated names (``<table>_<column>_<hash>``)
    are found without hard coding a hash that Django is free to change.
    """
    connection_ = connections[using]
    with connection_.cursor() as cursor:
        db_constraints = connection_.introspection.get_constraints(cursor, table)
    found = []
    for name, details in db_constraints.items():
        is_index = details.get('index')
        is_unique = bool(details.get('unique'))
        if not is_index and (not is_unique or name.startswith('__unnamed')):
            # not an index at all, or an unnamed inline UNIQUE column
            continue
        if columns is not None and tuple(details['columns']) != tuple(columns):
            continue
        if unique is not None and is_unique != unique:
            continue
        found.append(name)
    return sorted(found)


def drop_index(table, columns=None, name=None, unique=None, using='default'):
    """Drop one index of ``table``, chosen by name or by columns."""
    if name is None:
        candidates = index_names(table, columns=columns, unique=unique, using=using)
        if len(candidates) != 1:
            raise AssertionError('Expected exactly one index on %s%s, found %s' % (table, tuple(columns or ()), candidates))
        name = candidates[0]
    connection_ = connections[using]
    with connection_.cursor() as cursor:
        cursor.execute('DROP INDEX %s' % name)
    return name


def drop_table(table, using='default'):
    connection_ = connections[using]
    with connection_.cursor() as cursor:
        cursor.execute('DROP TABLE %s' % table)


def create_index(name, table, columns, unique=False, using='default'):
    """Create an index the way Django does, with quoted identifiers."""
    connection_ = connections[using]
    quoted = ', '.join('"%s"' % column for column in columns)
    statement = 'CREATE %sINDEX "%s" ON "%s" (%s)' % ('UNIQUE ' if unique else '', name, table, quoted)
    with connection_.cursor() as cursor:
        cursor.execute(statement)
    return name


def rebuild_table(table, ddl, keep_indexes=None, using='default'):
    """Replace ``table`` with a table built from ``ddl``.

    SQLite can drop an index but never an inline ``UNIQUE`` column constraint,
    so removing one means rebuilding the table. Every index of the old table is
    recreated afterwards, except the ones named in ``keep_indexes`` when a
    subset is given.

    ``ddl`` must declare the same columns in the same order as the table it
    replaces, because the rows are copied with ``SELECT *``. It must contain a
    ``{table}`` placeholder, which is replaced by the temporary table name.
    """
    connection_ = connections[using]
    saved = index_ddl(table, using=using)
    if keep_indexes is None:
        keep_indexes = sorted(saved)
    else:
        missing = [name for name in keep_indexes if name not in saved]
        if missing:
            raise AssertionError('Unknown index to keep: %s' % ', '.join(missing))
    temporary = '%s__rebuild' % table
    with connection_.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS %s' % temporary)
        cursor.execute(ddl.replace('{table}', temporary))
        cursor.execute('INSERT INTO %s SELECT * FROM %s' % (temporary, table))
        cursor.execute('DROP TABLE %s' % table)
        cursor.execute('ALTER TABLE %s RENAME TO %s' % (temporary, table))
        for name in keep_indexes:
            cursor.execute(saved[name])
    return sorted(saved)


def model1_ddl(without_unique=(), without_constraint=(), extra_constraints=()):
    """The DDL of the model1 table, minus the parts a test wants to remove."""
    return _table_ddl(MODEL1_COLUMNS, MODEL1_UNIQUE_COLUMNS, MODEL1_CONSTRAINTS, without_unique, without_constraint, extra_constraints)


def _table_ddl(columns, unique_columns, constraints, without_unique, without_constraint, extra_constraints):
    for name in without_constraint:
        if name not in constraints:
            raise AssertionError('Unknown constraint %r' % name)
    definitions = []
    for name, definition in columns:
        if name in unique_columns and name not in without_unique:
            definition = '%s UNIQUE' % definition
        definitions.append('"%s" %s' % (name, definition))
    clauses = definitions + [ddl for name, ddl in constraints.items() if name not in without_constraint] + list(extra_constraints)
    return 'CREATE TABLE {table} (%s)' % ', '.join(clauses)
