# Copyright 2022 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import mimetypes
import os
import re

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    is_save_in_cmis_enabled = fields.Boolean(
        string="Save attachments in CMIS",
        default=False,
    )
    allowed_cmis_folder_field_ids = fields.Many2many(
        comodel_name="ir.model.fields",
        compute="_compute_cmis_folder_fields",
    )
    is_multiple_cmis_fields = fields.Boolean(
        compute="_compute_cmis_folder_fields",
    )
    cmis_folder_field_id = fields.Many2one(
        string="CMIS Folder",
        comodel_name="ir.model.fields",
        domain="[('id', 'in', allowed_cmis_folder_field_ids)]",
        compute="_compute_cmis_folder_field_id",
        store=True,
        readonly=False,
    )
    cmis_duplicate_handler = fields.Selection(
        selection=[
            ("use_existing", "Use existing"),
            ("error", "Raise exception"),
            ("new_version", "Create a new version"),
            ("increment", "Rename as file(X).pdf"),
        ],
        string="Duplicate strategy",
        default="increment",
    )

    @api.depends("model")
    def _compute_cmis_folder_fields(self):
        for rec in self:
            cmis_fields = self.env["ir.model.fields"]
            if rec.model:
                cmis_fields = cmis_fields.sudo().search(
                    [("model", "=", rec.model), ("ttype", "=", "cmis_folder")]
                )
            rec.allowed_cmis_folder_field_ids = cmis_fields
            rec.is_multiple_cmis_fields = len(cmis_fields) > 1

    @api.depends("allowed_cmis_folder_field_ids")
    def _compute_cmis_folder_field_id(self):
        for rec in self:
            if rec.cmis_folder_field_id not in rec.allowed_cmis_folder_field_ids:
                rec.cmis_folder_field_id = rec.allowed_cmis_folder_field_ids[:1]

    def _get_cmis_parent_folder(self, related_record):
        self.ensure_one()
        field_name = self.cmis_folder_field_id.sudo().name
        field = related_record._fields[field_name]
        cmis_backend = field.get_backend(self.env)
        root_objectId = related_record[field_name]
        if not root_objectId:
            field.create_value(related_record)
            root_objectId = related_record[field_name]
        return cmis_backend.get_cmis_repository().get_object(root_objectId)

    @api.model
    def get_mimetype(self, file_name):
        return mimetypes.guess_type(file_name)[0]

    @api.model
    def _sanitize_query_arg(self, arg):
        return arg.replace("\\", "\\\\").replace("'", "\\'")

    def _cmis_document_exists(self, cmis_parent_folder, file_name):
        """Return the document named file_name in the folder, or None"""
        cmis_qry = (
            "SELECT cmis:objectId FROM cmis:document WHERE "
            f"IN_FOLDER('{cmis_parent_folder.id}') AND "
            f"cmis:name='{self._sanitize_query_arg(file_name)}'"
        )
        _logger.debug("Query CMIS with %s", cmis_qry)
        repo = cmis_parent_folder.repository
        page = repo.query(cmis_qry, max_items=1)
        if not page.objects:
            return None
        return repo.get_object(page.objects[0].id)

    def _get_incremented_name(self, cmis_parent_folder, file_name):
        """Return file_name suffixed by (X), X being the highest suffix
        already used in the folder plus 1: file(1).pdf, file(2).pdf..."""
        name, ext = os.path.splitext(file_name)

        def like(value):
            return (
                self._sanitize_query_arg(value).replace("%", "\\%").replace("_", "\\_")
            )

        cmis_qry = (
            "SELECT cmis:name FROM cmis:document WHERE "
            f"IN_FOLDER('{cmis_parent_folder.id}') AND "
            f"cmis:name LIKE '{like(name)}(%){like(ext)}'"
        )
        pattern = re.compile(re.escape(name) + r"\((\d+)\)" + re.escape(ext) + "$")
        nums = [0]
        for doc in cmis_parent_folder.repository.query(cmis_qry).objects:
            match = pattern.match(doc.name or "")
            if match:
                nums.append(int(match.group(1)))
        return f"{name}({max(nums) + 1}){ext}"

    def _save_attachments_in_cmis(self, related_record):
        self.ensure_one()
        cmis_parent_folder = self._get_cmis_parent_folder(related_record)
        for attachment in self.attachment_ids:
            file_name = attachment.name
            content = attachment.raw
            existing = self._cmis_document_exists(cmis_parent_folder, file_name)
            if existing and self.cmis_duplicate_handler == "error":
                raise UserError(
                    self.env._('Document "%s" already exists in CMIS', file_name)
                )
            if not existing or self.cmis_duplicate_handler == "increment":
                if existing:
                    file_name = self._get_incremented_name(
                        cmis_parent_folder, file_name
                    )
                self._create_cmis_document(content, file_name, cmis_parent_folder)
            elif self.cmis_duplicate_handler == "new_version":
                self._update_cmis_document(content, file_name, existing)
            # use_existing: the existing document is kept

    def _create_cmis_document(self, content, file_name, cmis_parent_folder):
        self.ensure_one()
        props = {
            "cmis:name": file_name,
        }
        mimetype = self.get_mimetype(file_name)
        return cmis_parent_folder.create_document(
            file_name,
            content,
            mimetype,
            properties=props,
        )

    def _update_cmis_document(self, content, file_name, cmis_doc):
        self.ensure_one()
        mimetype = self.get_mimetype(file_name)
        pwc = cmis_doc.check_out()
        return cmis_doc.repository.check_in(
            pwc.id,
            content,
            mimetype,
            major=False,
            comment=self.env._("Saved from Odoo mail composer"),
            filename=file_name,
        )

    def _action_send_mail(self, auto_commit=False):
        res = super()._action_send_mail(auto_commit=auto_commit)
        for rec in self:
            if (
                rec.is_save_in_cmis_enabled
                and rec.cmis_folder_field_id
                and rec.model
                and rec.composition_mode == "comment"
            ):
                for related_record in self.env[rec.model].browse(
                    rec._evaluate_res_ids()
                ):
                    rec._save_attachments_in_cmis(related_record)
        return res
