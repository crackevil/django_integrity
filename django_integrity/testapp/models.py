from django.db import models
import django

#: Django before 4.1 took the condition of a CheckConstraint as ``check``, since
#: 4.1 it is ``condition``.
CHECK_CONDITION_KWARG = 'check' if django.VERSION < (4, 1) else 'condition'


def check_constraint(condition, name):
    "A CheckConstraint built with whichever keyword this Django version takes."
    return models.CheckConstraint(**{CHECK_CONDITION_KWARG: condition}, name=name)

class Model1(models.Model):
    f1 = models.IntegerField(db_column='aaaa')
    uf1 = models.IntegerField(unique=True, db_column='gerd')
    uf2 = models.IntegerField(unique=False, db_column='dhff')
    uf3 = models.CharField(max_length=254, unique=True, db_column='jy')
    uf4 = models.CharField(max_length=254, unique=False, db_column='vh')
    if1 = models.IntegerField(db_index=True, db_column='tu')
    if2 = models.IntegerField(db_index=False, db_column='few')
    if3 = models.CharField(max_length=254, db_index=True, db_column='fn')
    if4 = models.CharField(max_length=254, db_index=False, db_column='uyk')
    iuf1 = models.IntegerField(db_index=True, unique=True, db_column='dfb')
    iuf2 = models.IntegerField(db_index=True, unique=False, db_column='dgn')
    iuf3 = models.IntegerField(db_index=False, unique=True, db_column='qsdf')
    iuf4 = models.CharField(max_length=254, db_index=True, unique=True, db_column='jhj')
    iuf5 = models.CharField(max_length=254, db_index=True, unique=False, db_column='cb')
    iuf6 = models.CharField(max_length=254, db_index=False, unique=True, db_column='hty')

    class Meta:
        unique_together = (('uf1', 'f1'), ('if1', 'f1'))
        indexes = [
            models.Index(fields=('f1', '-if1'), name='m1_f1_if1_idx'),
            models.Index(fields=('if1', 'f1'), name='m1_if1_f1_idx'),
            models.Index(fields=('if3', '-uf4'), name='m1_if3_uf4_idx'),
            models.Index(fields=('uf2',), name='m1_uf2_partial_idx', condition=models.Q(uf2__gte=0)),
        ]
        constraints = [
            models.UniqueConstraint(fields=('uf3', 'uf4'), name='m1_uf3_uf4_uniq'),
            check_constraint(models.Q(f1__gte=1), name='cq_f1'),
            check_constraint(models.Q(uf1__gte=1) & models.Q(iuf1__gte=1), name='cq_2'),
        ]


