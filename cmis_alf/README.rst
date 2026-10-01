.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=================================
CMIS Connector Alfresco Extension
=================================

This module extend the CMIS connector with specifics functionalities provided by alfresco:

* Open CMIS content into Alfresco Share
* Client for the Alfresco public REST API v1 (``odoo.addons.cmis_alf.alfresco_client``)
* Create a folder from a template folder (copy of the whole tree)


Documentation: `alfodoo.org <http://alfodoo.org>`_ 

Configuration
=============

On the CMIS backend, set:

* **Location**: the CMIS browser binding URL, e.g.
  ``http://localhost:8080/alfresco/api/-default-/public/cmis/versions/1.1/browser/``
* **Alfresco Api Url**: the public REST API v1 URL, e.g.
  ``http://localhost:8080/alfresco/api/-default-/public/alfresco/versions/1``
* **Alfresco Share Url**, e.g. ``http://localhost:8080/share``


Credits
=======

Contributors
------------

* Laurent Mignon <laurent.mignon@acsone.eu>
* tansadio <tansadio@gmail.com>

Maintainer
----------

.. image:: https://www.acsone.eu/logo.png
   :alt: ACSONE SA/NV
   :target: http://www.acsone.eu

This module is maintained by ACSONE SA/NV.
