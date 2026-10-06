# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

# DON'T IMPORT THIS MODULE IN INIT TO AVOID THE CREATION OF THE MODELS
# DEFINED FOR TESTS INTO YOUR ODOO INSTANCE

from odoo import fields, models

from odoo.addons.cmis_field.fields import CmisFolder


class CmisMailTestModel(models.Model):
    _name = "cmis.mail.test.model"
    _description = "cmis.mail.test.model Fake Model"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    cmis_folder = CmisFolder(backend_name="cmis_mail_test")
