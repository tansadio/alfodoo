# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from unittest import mock

from odoo.tests import common, new_test_user

from odoo.addons.cmis.tests.common import FakeSession, make_response

from ..alfresco_client import AlfrescoRestClient


class TestCmisBackendAlfresco(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = cls.env["cmis.backend"].create(
            {
                "name": "Alfresco",
                "location": "http://alfresco/browser/",
                "username": "admin",
                "password": "admin",
            }
        )

    def test_defaults(self):
        self.assertEqual(
            self.backend.alfresco_api_location,
            "http://localhost:8080/alfresco/api/-default-/public/alfresco/versions/1",
        )
        client = self.backend.get_alfresco_client()
        self.assertEqual(client.url, self.backend.alfresco_api_location)
        self.assertEqual(client.session.auth, ("admin", "admin"))

    def test_get_alfresco_client_as_user(self):
        user = new_test_user(self.env, login="cmis_alf_user", groups="base.group_user")
        client = self.backend.with_user(user).get_alfresco_client()
        self.assertEqual(client.session.auth, ("admin", "admin"))

    def test_cmis_objectid_from_noderef(self):
        self.assertEqual(
            self.backend._get_cmis_objectid_from_noderef(
                "workspace://SpacesStore/1c8007c5-da05-4889-83e1-c8c43dbf4683"
            ),
            "1c8007c5-da05-4889-83e1-c8c43dbf4683",
        )

    def test_create_cmis_folder_from_template(self):
        session = FakeSession(
            make_response(json_data={"entry": {"id": "new"}}),
            make_response(json_data={"entry": {"id": "new"}}),
        )
        client = AlfrescoRestClient(
            self.backend.alfresco_api_location, "admin", "admin", session=session
        )
        with mock.patch.object(
            type(self.backend), "get_alfresco_client", return_value=client
        ):
            object_id = self.backend.create_cmis_folder_from_template(
                "tpl", "parent;1.0", "Client X", title="Client X SA"
            )
        self.assertEqual(object_id, "new")
        copy, update = session.calls
        self.assertTrue(copy[1].endswith("/nodes/tpl/copy"))
        self.assertEqual(copy[2]["json"]["targetParentId"], "parent")
        self.assertTrue(update[1].endswith("/nodes/new"))
        self.assertEqual(
            update[2]["json"]["properties"],
            {"cm:title": "Client X SA", "cm:description": ""},
        )
