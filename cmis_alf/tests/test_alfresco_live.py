# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Tests against a real Alfresco, run only when it is configured with
``CMIS_TEST_LOCATION`` (CMIS browser binding URL) and ``ALFRESCO_TEST_API``
(REST API v1 URL), ``CMIS_TEST_USERNAME`` and ``CMIS_TEST_PASSWORD``
(default admin / admin)."""

import os
import unittest
import uuid

from odoo.tests import common

LOCATION = os.environ.get("CMIS_TEST_LOCATION")
API = os.environ.get("ALFRESCO_TEST_API")


@unittest.skipUnless(LOCATION and API, "CMIS_TEST_LOCATION or ALFRESCO_TEST_API unset")
class TestAlfrescoLive(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["cmis.backend"].create(
            {
                "name": "Alfresco live",
                "location": LOCATION,
                "alfresco_api_location": API,
                "username": os.environ.get("CMIS_TEST_USERNAME", "admin"),
                "password": os.environ.get("CMIS_TEST_PASSWORD", "admin"),
            }
        )
        repo = cls.backend.get_cmis_repository()
        cls.folder = repo.get_root_folder().create_folder(
            f"odoo-cmis-alf-test-{uuid.uuid4().hex}"
        )
        cls.addClassCleanup(cls.folder.delete_tree)

    def test_create_cmis_folder_from_template(self):
        template = self.folder.create_folder("Template")
        template.create_folder("Contrats")
        template.create_folder("Factures")
        object_id = self.backend.create_cmis_folder_from_template(
            template.id, self.folder.id, "Client X", title="Client X SA"
        )
        repo = self.backend.get_cmis_repository()
        new_folder = repo.get_object(object_id)
        self.assertEqual(new_folder.name, "Client X")
        self.assertEqual(new_folder.properties["cm:title"], "Client X SA")
        self.assertEqual(
            sorted(child.name for child in new_folder.iter_children()),
            ["Contrats", "Factures"],
        )
        noderef = self.backend._get_alf_noderef_from_objectid(object_id)
        self.assertEqual(noderef, f"workspace://SpacesStore/{object_id}")
