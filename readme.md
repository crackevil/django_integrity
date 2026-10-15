## django integrity

This library works for django integrity, including indexes and constraints, between model definition and real database scheme.

at model definition level, it need handle these:
* model meta defined indexes and constraints
* model class defined `unique_together` and `indexes_together`
* field defined `unique=True` and `db_index=True`

the library functions:
* get intersection collection of integrity between model definition and real database scheme
* return integrity collection only in model definition but not in real database scheme
