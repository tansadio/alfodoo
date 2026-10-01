# Copyright 2026 tansadio
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
"""Minimal client for the Alfresco public REST API v1.

It covers what CMIS does not: copying a folder tree (folder templates),
aspects and Alfresco specific node information. See
https://docs.alfresco.com/content-services/latest/develop/rest-api-guide/
"""

import logging

import requests

from odoo.addons.cmis.exceptions import (
    CMISConnectionError,
    CMISContentAlreadyExistsError,
    CMISError,
    CMISObjectNotFoundError,
    CMISPermissionDeniedError,
)

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

ERRORS_BY_STATUS = {
    403: CMISPermissionDeniedError,
    404: CMISObjectNotFoundError,
    409: CMISContentAlreadyExistsError,
}


def node_id_from_object_id(object_id):
    """Return the Alfresco node id of a CMIS object id.

    CMIS ids of documents carry a version label (``<node id>;1.0``) and
    Alfresco node references a store prefix (``workspace://SpacesStore/<id>``).
    """
    return object_id.split(";")[0].split("/")[-1]


class AlfrescoRestClient:
    def __init__(self, url, username, password, timeout=DEFAULT_TIMEOUT, session=None):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.auth = (username, password)

    def request(self, method, path, **kwargs):
        """Send a request to the API and return the decoded JSON ``entry``"""
        url = f"{self.url}/{path.lstrip('/')}"
        kwargs.setdefault("timeout", self.timeout)
        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as error:
            _logger.warning("Alfresco request to %s failed: %s", url, error)
            raise CMISConnectionError(
                f"Unable to reach Alfresco {url}: {error}"
            ) from error
        if response.status_code >= 400:
            raise self._error_from_response(response)
        if not response.content:
            return {}
        return response.json().get("entry", {})

    def _error_from_response(self, response):
        try:
            error = response.json().get("error", {})
        except ValueError:
            error = {}
        message = error.get("briefSummary") or response.reason or "Alfresco error"
        if response.status_code == 401:
            error_class = CMISConnectionError
            message = f"Alfresco authentication failed: {message}"
        else:
            error_class = ERRORS_BY_STATUS.get(response.status_code, CMISError)
        return error_class(
            message,
            cmis_exception=error.get("errorKey"),
            status_code=response.status_code,
        )

    def get_node(self, node_id, include=None):
        params = {"include": ",".join(include)} if include else None
        return self.request("GET", f"nodes/{node_id}", params=params)

    def copy_node(self, node_id, target_parent_id, name=None):
        """Copy a node, and all its children for a folder"""
        payload = {"targetParentId": target_parent_id}
        if name:
            payload["name"] = name
        return self.request("POST", f"nodes/{node_id}/copy", json=payload)

    def update_node(self, node_id, name=None, properties=None, aspect_names=None):
        payload = {}
        if name:
            payload["name"] = name
        if properties:
            payload["properties"] = properties
        if aspect_names is not None:
            payload["aspectNames"] = aspect_names
        return self.request("PUT", f"nodes/{node_id}", json=payload)
