# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Tests against a real CMIS server, run only when ``CMIS_TEST_LOCATION``
(browser binding URL) is set, with ``CMIS_TEST_USERNAME`` and
``CMIS_TEST_PASSWORD`` (default admin / admin)."""

import os
import unittest
import uuid

from odoo.tools import mute_logger

from .test_ir_actions_report import CmisReportCase

LOCATION = os.environ.get("CMIS_TEST_LOCATION")


@unittest.skipUnless(LOCATION, "CMIS_TEST_LOCATION is not set")
class TestCmisReportWriteLive(CmisReportCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cmis_backend.write(
            {
                "location": LOCATION,
                "username": os.environ.get("CMIS_TEST_USERNAME", "admin"),
                "password": os.environ.get("CMIS_TEST_PASSWORD", "admin"),
                "initial_directory_write": f"/odoo-report-test-{uuid.uuid4().hex}",
            }
        )

    def setUp(self):
        super().setUp()
        # no mock of get_unique_folder_name: use the real CMIS queries
        self.patched_get_unique_folder_name.stop()
        self.addCleanup(self._remove_root)

    def _remove_root(self):
        folder = self.cmis_backend.get_folder_by_path(
            self.cmis_backend.initial_directory_write, create_if_not_found=False
        )
        if folder:
            folder.delete_tree()

    def _documents(self):
        repo = self.cmis_backend.get_cmis_repository()
        folder = repo.get_object(self.inst.cmis_folder)
        return {doc.name: doc for doc in folder.iter_children()}

    @mute_logger("odoo.addons.base.models.assetsbundle")
    def test_live_save_report(self):
        # the folder of the record is created on demand, then the report
        self.action_report._render(self.report, self.inst.ids)
        documents = self._documents()
        self.assertEqual(list(documents), ["folder_name.pdf"])
        self.assertEqual(documents["folder_name.pdf"].get_content(), self.pdf_content_1)
        self.assertEqual(documents["folder_name.pdf"].version_label, "1.0")

        self.report.cmis_duplicate_handler = "new_version"
        self.mocked_wkhtmltopdf.return_value = self.pdf_content_2 + b"\n%v2"
        self.action_report._render(self.report, self.inst.ids)
        document = self._documents()["folder_name.pdf"]
        self.assertEqual(document.version_label, "1.1")
        self.assertTrue(document.get_content().endswith(b"%v2"))

        self.report.cmis_duplicate_handler = "increment"
        self.action_report._render(self.report, self.inst.ids)
        self.assertEqual(
            sorted(self._documents()), ["folder_name(1).pdf", "folder_name.pdf"]
        )

        self.report.cmis_duplicate_handler = "use_existing"
        self.mocked_wkhtmltopdf.return_value = b"%PDF-not-used"
        res = self.action_report._render(self.report, self.inst.ids)
        self.assertTrue(res[0].endswith(b"%v2"))
        self.assertEqual(len(self._documents()), 2)
