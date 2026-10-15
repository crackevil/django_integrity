
from django.core.management.base import BaseCommand
from django.apps import apps
from django_integrity.base import DjangoModelIntegrityDiffExecutor_SchemeEditor, DjangoModelIntegrityDiffExecutor_Migration

class Command(BaseCommand):
	help = 'fill lost integrity not exist in database'

	def add_arguments(self, parser):
		parser.add_argument('app_label', type=str, help="Target application label")
		parser.add_argument('model_name', type=str, help="Target model")
		parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False, help="print sql instead of executing it")

	def handle(self, app_label, model_name, dry_run=False, *args, **options):
		app_config = apps.get_app_config(app_label)
		model = app_config.get_model(model_name)
		executor = DjangoModelIntegrityDiffExecutor_SchemeEditor(model, bool(dry_run))
		sqls = executor.fill_lost()
		if sqls:
			for s in sqls:
				print(s)



