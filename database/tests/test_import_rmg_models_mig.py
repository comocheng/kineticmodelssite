import os
import shutil
import tempfile
from unittest import mock

from django_test_migrations.contrib.unittest_case import MigratorTestCase

from database.tests.test_import_rmg_species_unit import model_folder


class TestImportRmgModelsIntegration(MigratorTestCase):
    """The import_rmg_models migration no longer imports (see its docstring)."""

    migrate_from = ("database", "0001_initial")
    migrate_to = ("database", "import_rmg_models")

    def prepare(self):
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory)
        model_folder(directory, "model", ["H", "OH"], kinetics=True)
        environment = mock.patch.dict(os.environ, {"RMGMODELSPATH": directory})
        environment.start()
        self.addCleanup(environment.stop)

    def test_imports_no_models(self):
        for name in ("KineticModel", "Species", "Reaction"):
            model = self.new_state.apps.get_model("database", name)
            self.assertFalse(model.objects.exists(), name)
