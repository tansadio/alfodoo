# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from unittest import mock

from odoo.exceptions import UserError

from odoo.addons.cmis.client import CmisPage

from .common import CmisMailCase


class TestMailComposeMessage(CmisMailCase):
    def setUp(self):
        super().setUp()
        self.folder = mock.MagicMock(id="folder_id")
        self.repo = self.folder.repository
        self.repo.query.return_value = CmisPage([], False, 0)
        patcher = mock.patch.object(
            type(self.env["mail.compose.message"]),
            "_get_cmis_parent_folder",
            return_value=self.folder,
        )
        self.get_parent = patcher.start()
        self.addCleanup(patcher.stop)

    def _existing(self, *names):
        """The query of the existing documents returns these names"""
        objects = []
        for name in names:
            obj = mock.MagicMock(id=f"{name};1.0")
            obj.name = name
            objects.append(obj)
        self.repo.query.return_value = CmisPage(objects, False, len(objects))
        self.repo.get_object.side_effect = lambda object_id: next(
            o for o in objects if o.id == object_id
        )

    def test_cmis_folder_fields(self):
        composer = self.composer()
        self.assertEqual(composer.allowed_cmis_folder_field_ids, self.folder_field)
        self.assertEqual(composer.cmis_folder_field_id, self.folder_field)
        self.assertFalse(composer.is_multiple_cmis_fields)
        # no cmis folder on the partners
        composer = self.composer(records=self.partner)
        self.assertFalse(composer.allowed_cmis_folder_field_ids)
        self.assertFalse(composer.cmis_folder_field_id)

    def test_disabled(self):
        self.composer().action_send_mail()
        self.get_parent.assert_not_called()
        self.folder.create_document.assert_not_called()

    def test_save_attachments(self):
        self.composer(is_save_in_cmis_enabled=True).action_send_mail()
        self.get_parent.assert_called_once()
        self.assertEqual(self.get_parent.call_args[0][0], self.record)
        name, content, mimetype = self.folder.create_document.call_args[0]
        self.assertEqual(
            (name, content, mimetype),
            ("contrat.pdf", b"%PDF contrat", "application/pdf"),
        )
        # the message is posted as usual
        self.assertIn("Voici le contrat", self.record.message_ids[0].body)

    def test_duplicate_error(self):
        # an existing document: error, nothing created
        self._existing("contrat.pdf")
        composer = self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="error"
        )
        with self.assertRaises(UserError):
            composer.action_send_mail()
        self.folder.create_document.assert_not_called()

    def test_duplicate_error_no_existing(self):
        # no existing document: created, no error
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="error"
        ).action_send_mail()
        self.folder.create_document.assert_called_once()

    def test_duplicate_increment(self):
        self._existing("contrat.pdf", "contrat(1).pdf")
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="increment"
        ).action_send_mail()
        self.assertEqual(self.folder.create_document.call_args[0][0], "contrat(2).pdf")

    def test_duplicate_new_version(self):
        self._existing("contrat.pdf")
        existing = self.repo.get_object("contrat.pdf;1.0")
        existing.check_out.return_value = mock.MagicMock(id="contrat.pdf;pwc")
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="new_version"
        ).action_send_mail()
        self.folder.create_document.assert_not_called()
        pwc_id, content = existing.repository.check_in.call_args[0][:2]
        self.assertEqual((pwc_id, content), ("contrat.pdf;pwc", b"%PDF contrat"))

    def test_duplicate_use_existing(self):
        self._existing("contrat.pdf")
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="use_existing"
        ).action_send_mail()
        self.folder.create_document.assert_not_called()

    def test_batch(self):
        other = self.record.copy({"name": "Autre dossier"})
        records = self.record + other
        self.composer(records=records, is_save_in_cmis_enabled=True).action_send_mail()
        self.assertEqual(
            [call[0][0] for call in self.get_parent.call_args_list],
            [self.record, other],
        )
