# Copyright 2016 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

CMIS_NAME_INVALID_CHARS = r'\/:*?"<>|'
CMIS_NAME_INVALID_CHARS_RX = "[" + re.escape(CMIS_NAME_INVALID_CHARS) + "]"


class CmisBackend(models.Model):
    _inherit = "cmis.backend"

    @api.constrains("sanitize_replace_char")
    def _check_sanitize_replace_char(self):
        for rec in self:
            rc = rec.sanitize_replace_char
            if rc and re.findall(CMIS_NAME_INVALID_CHARS_RX, rc):
                raise ValidationError(
                    self.env._(
                        "The character to use as replacement can not be one of '%s'",
                        CMIS_NAME_INVALID_CHARS,
                    )
                )

    enable_sanitize_cmis_name = fields.Boolean(
        "Sanitize name on content creation?",
        help="If checked, the name of the CMIS content created by the "
        "CMIS fields will be sanitized by replacing the characters not "
        "supported in a cmis:name with the one specified.",
        default=True,
    )
    sanitize_replace_char = fields.Char(
        "Replacement char",
        help="Character used as replacement of invalid characters found in"
        "the value to use as cmis:name by the sanitize method",
        default="_",
    )
    folder_name_conflict_handler = fields.Selection(
        selection=[
            ("error", "Raise exception"),
            ("increment", 'Create as "name_(X)"'),
        ],
        string="Strategy in case of duplicate",
        required=True,
        default="error",
    )

    @api.model
    def _get_web_description(self, record):
        """Return the desciption of backend record to be included into the
        field description of cmis fields that reference the backend.
        """
        return {"id": record.id, "name": record.name, "location": record.location}

    def get_web_description(self):
        """Return informations to be included into the field description of
        cmis fields that reference the backend.
        """
        ret = {}
        for this in self:
            ret[this.id] = self._get_web_description(this)
        return ret

    @api.model
    def get_by_name(self, name, raise_if_not_found=True):
        # simple case: one backend
        domain = [(1, "=", 1)]
        if name:
            # multi backends case
            domain = [("name", "=", name)]
        backend = self.search(domain)
        if len(backend) != 1 and raise_if_not_found:
            if name:
                msg = self.env._(
                    "Expected 1 backend named %(name)s, %(number)s found",
                    name=name,
                    number=len(backend),
                )
            else:
                msg = self.env._("No backend found")
            raise UserError(msg)
        return backend

    @api.model
    def is_valid_cmis_name(self, name, raise_if_invalid=False):
        if (
            re.findall(CMIS_NAME_INVALID_CHARS_RX, name)
            or name.startswith(" ")
            or name.endswith(" ")
            or name.endswith(".")
        ):
            if not raise_if_invalid:
                return False
            raise UserError(
                self.env._(
                    "%(name)s is not a valid name.\n"
                    "The following chars are not allowed %(invalid_chars)s and "
                    "the name can not ends with a space or a '.'",
                    name=name,
                    invalid_chars=CMIS_NAME_INVALID_CHARS,
                )
            )
        return True

    def sanitize_cmis_name(self, value, replace_char=None):
        """Replace chars not allowed in cmis by the value of replace_char.
        If replace_char is None, the character used to subsitute invalid chars
        is the one defined by the sanitize_replace_char field
        """
        self.ensure_one()
        if replace_char is None:
            replace_char = self.sanitize_replace_char or ""
        while value.endswith("."):
            value = value[:-1]
        return re.sub(CMIS_NAME_INVALID_CHARS_RX, replace_char, value.strip()).strip()

    def sanitize_cmis_names(self, values, replace_char=None):
        """Sanitize a list of values"""
        return [self.sanitize_cmis_name(v, replace_char) for v in values]

    def get_folder_by_path_parts(
        self, path_parts, create_if_not_found=True, cmis_parent_objectid=None
    ):
        """Return the cmis object for the specified path parts.
        The path is build from path_parts where each part is sanitized if
        `enable_sanitize_cmis_name` is True on the backend instance
        """
        self.ensure_one()
        if self.enable_sanitize_cmis_name:
            path_parts = self.sanitize_cmis_names(path_parts)
        path = "/".join(path_parts)
        return self.get_folder_by_path(path, create_if_not_found, cmis_parent_objectid)

    def get_unique_folder_name(self, name, parent, conflict_handler=None):
        """Return a unique name for a folder into its parent.

        Check if the name already exists into the parent.
        If the name already exists:
         if backend.folder_name_conflict_handler == 'error'
            ValidationError is raised
         if backend.folder_name_conflict_handler == 'increment'
            return a new name with suffix '_(X)'
        :param parent: the parent folder, as cmis:objectId or CmisObject
        :return: a unique name
        """
        self.ensure_one()
        conflict_handler = conflict_handler or self.folder_name_conflict_handler
        parent_id = getattr(parent, "id", parent)
        repo = self.get_cmis_repository()
        quoted_name = name.replace("\\", "\\\\").replace("'", "\\'")
        cmis_qry = (
            "SELECT cmis:objectId FROM cmis:folder WHERE "
            f"IN_FOLDER('{parent_id}') AND cmis:name='{quoted_name}'"
        )
        if not repo.query(cmis_qry, max_items=1).objects:
            return name
        if conflict_handler == "error":
            raise ValidationError(
                self.env._('Folder "%s" already exists in CMIS', name)
            )
        # increment: find the highest suffix already used
        cmis_qry = (
            "SELECT cmis:name FROM cmis:folder WHERE "
            f"IN_FOLDER('{parent_id}') AND "
            f"cmis:name LIKE '{self.sanitize_input(name)}\\_(%)'"
        )
        nums = [0]
        skip_count = 0
        while True:
            page = repo.query(cmis_qry, skip_count=skip_count)
            for folder in page.objects:
                num = re.findall(r"_\((\d+)\)$", folder.name or "")
                if num:
                    nums.append(int(num[0]))
            if not page.has_more_items or not page.objects:
                break
            skip_count += len(page.objects)
        return f"{name}_({max(nums) + 1})"
