# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Tests against a real CMIS server, run only when ``CMIS_TEST_LOCATION``
(browser binding URL) is set, with ``CMIS_TEST_USERNAME`` and
``CMIS_TEST_PASSWORD`` (default admin / admin)."""

import os
import unittest
import uuid

from odoo.exceptions import ValidationError

from .common import BaseTestCmis

LOCATION = os.environ.get("CMIS_TEST_LOCATION")


@unittest.skipUnless(LOCATION, "CMIS_TEST_LOCATION is not set")
class TestCmisFieldLive(BaseTestCmis):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cmis_backend.write(
            {
                "location": LOCATION,
                "username": os.environ.get("CMIS_TEST_USERNAME", "admin"),
                "password": os.environ.get("CMIS_TEST_PASSWORD", "admin"),
                "initial_directory_write": f"/odoo-cmis-field-test-{uuid.uuid4().hex}",
            }
        )
        cls.root_path = cls.cmis_backend.initial_directory_write

    def setUp(self):
        # no mock of get_unique_folder_name: use the real CMIS queries
        super(BaseTestCmis, self).setUp()
        self.addCleanup(self._remove_root)

    def _remove_root(self):
        folder = self.cmis_backend.get_folder_by_path(
            self.root_path, create_if_not_found=False
        )
        if folder:
            folder.delete_tree()

    def test_create_value(self):
        records = self.cmis_test_model.create(
            [{"name": "Client: A/B"}, {"name": "Client: A/B"}]
        )
        self.cmis_backend.folder_name_conflict_handler = "increment"
        records._fields["cmis_folder"].create_value(records)
        repo = self.cmis_backend.get_cmis_repository()
        first, second = (repo.get_object(r.cmis_folder) for r in records)
        # the names are sanitized, and suffixed when already used
        self.assertEqual(first.name, "Client_ A_B")
        self.assertEqual(second.name, "Client_ A_B_(1)")
        self.assertEqual(first.path, f"{self.root_path}/cmis_test_model/Client_ A_B")
        self.assertEqual(
            records[0]._fields["cmis_folder"].get_cmis_object(records[0]), first
        )

    def test_create_value_conflict_error(self):
        records = self.cmis_test_model.create([{"name": "Same"}, {"name": "Same"}])
        self.cmis_backend.folder_name_conflict_handler = "error"
        records[0]._fields["cmis_folder"].create_value(records[0])
        with self.assertRaises(ValidationError):
            records[1]._fields["cmis_folder"].create_value(records[1])
