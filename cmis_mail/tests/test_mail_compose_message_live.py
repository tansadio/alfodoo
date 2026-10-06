# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Tests against a real CMIS server, run only when ``CMIS_TEST_LOCATION``
(browser binding URL) is set, with ``CMIS_TEST_USERNAME`` and
``CMIS_TEST_PASSWORD`` (default admin / admin)."""

import os
import unittest
import uuid

from .common import CmisMailCase

LOCATION = os.environ.get("CMIS_TEST_LOCATION")


@unittest.skipUnless(LOCATION, "CMIS_TEST_LOCATION is not set")
class TestMailComposeMessageLive(CmisMailCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend.write(
            {
                "location": LOCATION,
                "username": os.environ.get("CMIS_TEST_USERNAME", "admin"),
                "password": os.environ.get("CMIS_TEST_PASSWORD", "admin"),
                "initial_directory_write": f"/odoo-mail-test-{uuid.uuid4().hex}",
            }
        )

    def setUp(self):
        super().setUp()
        self.addCleanup(self._remove_root)

    def _remove_root(self):
        folder = self.backend.get_folder_by_path(
            self.backend.initial_directory_write, create_if_not_found=False
        )
        if folder:
            folder.delete_tree()

    def _documents(self):
        repo = self.backend.get_cmis_repository()
        folder = repo.get_object(self.record.cmis_folder)
        return {doc.name: doc for doc in folder.iter_children()}

    def test_live_save_attachments(self):
        # the folder of the record is created on demand
        self.composer(is_save_in_cmis_enabled=True).action_send_mail()
        documents = self._documents()
        self.assertEqual(list(documents), ["contrat.pdf"])
        self.assertEqual(documents["contrat.pdf"].get_content(), b"%PDF contrat")
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="new_version"
        ).action_send_mail()
        self.assertEqual(self._documents()["contrat.pdf"].version_label, "1.1")
        self.composer(
            is_save_in_cmis_enabled=True, cmis_duplicate_handler="increment"
        ).action_send_mail()
        self.assertEqual(sorted(self._documents()), ["contrat(1).pdf", "contrat.pdf"])
