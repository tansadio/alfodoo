# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from types import MappingProxyType

from odoo_test_helper import FakeModelLoader

from odoo.tests import common, tagged


# the fake models change the registry: run once all the modules are loaded
@tagged("post_install", "-at_install")
class CmisMailCase(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()
        from .models import CmisMailTestModel

        cls.loader.update_registry((CmisMailTestModel,))
        # compute the fields of the ir.model.fields created for the fake
        # models now: they no longer exist once the test class rolled back
        cls.env.flush_all()
        cls.addClassCleanup(cls._restore_registry)
        cls.backend = cls.env["cmis.backend"].create(
            {
                "name": "cmis_mail_test",
                "location": "http://cmis/browser/",
                "username": "admin",
                "password": "secret",
                "initial_directory_write": "/odoo",
            }
        )
        cls.folder_field = cls.env["ir.model.fields"]._get(
            "cmis.mail.test.model", "cmis_folder"
        )
        cls.record = cls.env["cmis.mail.test.model"].create({"name": "Dossier"})
        cls.partner = cls.env["res.partner"].create(
            {"name": "Client", "email": "client@example.com"}
        )

    @classmethod
    def _restore_registry(cls):
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

    def composer(self, records=None, **values):
        records = records or self.record
        attachment = self.env["ir.attachment"].create(
            {"name": "contrat.pdf", "raw": b"%PDF contrat"}
        )
        return (
            self.env["mail.compose.message"]
            .with_context(
                default_model=records._name,
                default_res_ids=records.ids,
                default_composition_mode="comment",
            )
            .create(
                {
                    "subject": "Contrat",
                    "body": "<p>Voici le contrat</p>",
                    "partner_ids": [(6, 0, self.partner.ids)],
                    "attachment_ids": [(6, 0, attachment.ids)],
                    **values,
                }
            )
        )
