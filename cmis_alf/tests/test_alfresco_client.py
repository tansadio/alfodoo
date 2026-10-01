# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import BaseCase

from odoo.addons.cmis.exceptions import (
    CMISConnectionError,
    CMISContentAlreadyExistsError,
    CMISObjectNotFoundError,
)
from odoo.addons.cmis.tests.common import FakeSession, make_response

from ..alfresco_client import AlfrescoRestClient, node_id_from_object_id

API_URL = "http://alfresco/alfresco/api/-default-/public/alfresco/versions/1"


def alfresco_error(status, key, summary):
    return make_response(
        status,
        {"error": {"errorKey": key, "statusCode": status, "briefSummary": summary}},
    )


class TestAlfrescoClient(BaseCase):
    def _client(self, *responses):
        session = FakeSession(*responses)
        return AlfrescoRestClient(f"{API_URL}/", "admin", "secret", session=session)

    def test_node_id_from_object_id(self):
        self.assertEqual(node_id_from_object_id("abc;1.0"), "abc")
        self.assertEqual(node_id_from_object_id("abc;pwc"), "abc")
        self.assertEqual(node_id_from_object_id("workspace://SpacesStore/abc"), "abc")
        self.assertEqual(node_id_from_object_id("abc"), "abc")

    def test_copy_node(self):
        client = self._client(make_response(json_data={"entry": {"id": "new"}}))
        node = client.copy_node("tpl", "parent", name="Client X")
        self.assertEqual(node, {"id": "new"})
        method, url, kwargs = client.session.calls[0]
        self.assertEqual((method, url), ("POST", f"{API_URL}/nodes/tpl/copy"))
        self.assertEqual(
            kwargs["json"], {"targetParentId": "parent", "name": "Client X"}
        )
        self.assertEqual(client.session.auth, ("admin", "secret"))

    def test_update_node(self):
        client = self._client(make_response(json_data={"entry": {"id": "n"}}))
        client.update_node("n", properties={"cm:title": "T"}, aspect_names=[])
        method, url, kwargs = client.session.calls[0]
        self.assertEqual((method, url), ("PUT", f"{API_URL}/nodes/n"))
        self.assertEqual(
            kwargs["json"], {"properties": {"cm:title": "T"}, "aspectNames": []}
        )

    def test_get_node_include(self):
        client = self._client(make_response(json_data={"entry": {"id": "n"}}))
        client.get_node("n", include=["path", "aspectNames"])
        params = client.session.calls[0][2]["params"]
        self.assertEqual(params, {"include": "path,aspectNames"})

    def test_errors(self):
        client = self._client(
            alfresco_error(404, "framework.exception.EntityNotFound", "not found"),
            alfresco_error(409, "framework.exception.Conflict", "already exists"),
            make_response(401, {}, reason="Unauthorized"),
        )
        with self.assertRaises(CMISObjectNotFoundError) as error:
            client.get_node("nope")
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(CMISContentAlreadyExistsError):
            client.copy_node("tpl", "parent", name="existing")
        with self.assertRaises(CMISConnectionError):
            client.get_node("n")
