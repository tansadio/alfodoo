# © 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models

from ..alfresco_client import AlfrescoRestClient, node_id_from_object_id


class CmisBackend(models.Model):
    _inherit = "cmis.backend"

    share_location = fields.Char(
        string="Alfresco Share Url",
        required=True,
        default="http://localhost:8080/share",
    )
    alfresco_api_location = fields.Char(
        string="Alfresco Api Url",
        required=True,
        default="http://localhost:8080/alfresco/api/-default-/public/alfresco/versions/1",
        help="URL of the Alfresco public REST API v1",
    )

    def get_alfresco_client(self):
        """Return a client for the Alfresco public REST API v1"""
        self.ensure_one()
        # the credentials are only readable by the administrators
        backend = self.sudo()
        return AlfrescoRestClient(
            backend.alfresco_api_location,
            backend.username,
            backend.password,
            timeout=backend.timeout or None,
        )

    def _get_alf_noderef_from_objectid(self, cmis_objectid):
        """Return the Alfresco node reference of a CMIS object, like
        ``workspace://SpacesStore/1c8007c5-da05-4889-83e1-c8c43dbf4683``"""
        self.ensure_one()
        cmis_object = self.get_cmis_repository().get_object(cmis_objectid)
        return cmis_object.properties["alfcmis:nodeRef"]

    @api.model
    def _get_cmis_objectid_from_noderef(self, alf_noderef):
        """Return the CMIS object id of a folder from its Alfresco node
        reference (for folders, the object id is the node id)"""
        return node_id_from_object_id(alf_noderef)

    def create_cmis_folder_from_template(
        self, source_objectid, parent_objectid, name, title=None, description=None
    ):
        """Create a new folder as a copy of a template folder (with all its
        sub folders and documents) and return its CMIS object id."""
        self.ensure_one()
        client = self.get_alfresco_client()
        node = client.copy_node(
            node_id_from_object_id(source_objectid),
            node_id_from_object_id(parent_objectid),
            name=name,
        )
        properties = {"cm:title": title or "", "cm:description": description or ""}
        client.update_node(node["id"], properties=properties)
        return node["id"]
