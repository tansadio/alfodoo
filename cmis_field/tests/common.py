# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from contextlib import contextmanager
from types import MappingProxyType
from unittest import mock

from odoo_test_helper import FakeModelLoader

from odoo.tests import common, tagged


def cmis_object(object_id):
    """Return a mock of odoo.addons.cmis.client.CmisObject"""
    return mock.MagicMock(id=object_id)


@contextmanager
def mocked_cmis_repository():
    """Patch the CMIS repository of the backends. By default, the parent
    folder is found by path (``root_id``) and new folders get ``cmis_id``"""
    with mock.patch(
        "odoo.addons.cmis.models.cmis_backend.CmisBackend.get_cmis_repository"
    ) as mocked_get_repository:
        repository = mock.MagicMock()
        mocked_get_repository.return_value = repository
        repository.get_object_by_path.return_value = cmis_object("root_id")
        repository.create_folder.return_value = cmis_object("cmis_id")
        yield repository


# the fake models change the registry: run once all the modules are loaded
@tagged("post_install", "-at_install")
class BaseTestCmis(common.TransactionCase, FakeModelLoader):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()
        from .models import CmisTestModel, CmisTestModelInherits, CmisTestModelRelated

        cls.loader.update_registry(
            (CmisTestModel, CmisTestModelInherits, CmisTestModelRelated)
        )
        # compute the fields of the ir.model.fields created for the fake
        # models now: they no longer exist once the test class rolled back
        cls.env.flush_all()

        # mock commit since it"s called in the _auto_init method
        cls.cr.commit = mock.MagicMock()
        cls.cmis_test_model = cls.env["cmis.test.model"]
        cls.cmis_test_model_inherits = cls.env["cmis.test.model.inherits"]
        cls.cmis_test_model_related = cls.env["cmis.test.model.related"]
        cls.cmis_backend = cls.env.ref("cmis.cmis_backend_alfresco")
        cls.cmis_backend.initial_directory_write = "/odoo"

    def setUp(self):
        super().setUp()

        # global patch

        def get_unique_folder_name(name, parent):
            return name

        self.patched_get_unique_folder_name = mock.patch.object(
            self.cmis_backend.__class__,
            "get_unique_folder_name",
            side_effect=get_unique_folder_name,
        )
        self.patched_get_unique_folder_name.start()
        self.addCleanup(self.patched_get_unique_folder_name.stop)
        # We are replacing get_unique_folder_name by a mock. If Odoo asks
        # whether a method as _ondelete attr, the answer is always yes.
        # But there is no ondelete method on cmis_backend so we force it
        # to avoid calling it when deleting the record.
        self.cmis_backend.__class__._ondelete_methods = []

    @classmethod
    def tearDownClass(cls):
        original = cls.loader._original_registry
        cls.loader.restore_registry()
        # With Odoo 19, model._fields is a read-only view of model._fields__
        # and the fields are attributes of the model classes: restore_registry
        # only replaces model._fields by a copy and removes the attributes, so
        # the ORM would use other field objects. Restore them consistently.
        for name, model in cls.env.registry.models.items():
            fields_ = dict(original[name]["_fields"])
            model._fields__.clear()
            model._fields__.update(fields_)
            model._fields = MappingProxyType(model._fields__)
            for field_name, field in fields_.items():
                if vars(model).get(field_name) is not field:
                    setattr(model, field_name, field)
        super().tearDownClass()
