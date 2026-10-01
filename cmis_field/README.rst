
.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

==========
CMIS Field
==========

This module provides specialized fields to use to link an Odoo model with a
cmis content

Installation
============

In order to be able to use the functionalities provided by Odoo UI to add
custom field on an an existing model the server must be started with
*--load base,web,cmis_field*

Configuration
=============

In Settings -> Cmis -> backend Create a new CMIS backend with the host,
login and password.

Documentation: `alfodoo.org <http://alfodoo.org>`_

Usage
=====

.. code-block:: python

    from odoo import models

    from odoo.addons.cmis_field import fields as cmis_fields


    class ResPartner(models.Model):
        _inherit = "res.partner"

        cmis_folder = cmis_fields.CmisFolder(
            backend_name="alfresco",
            create_parent_get="_get_cmis_parent",  # optional
        )

The value is the ``cmis:objectId`` of the folder, stored as a ``varchar``.
``field.get_cmis_object(record)`` returns the folder as a
``odoo.addons.cmis.client.CmisObject``.

Changes in 19.0
===============

* ``CmisFolder`` is a subclass of ``fields.Char`` with its own type
  ``cmis_folder``: the storage and conversions are the ones of the Odoo ORM.
* The folder name defaults to the ``display_name`` of the record
  (``create_name_get``), ``name_get`` no longer exists.
* The CMIS calls use the browser binding client of the ``cmis`` module
  instead of ``cmislib``; ``get_create_parents`` returns object ids.
* The ``/web/cmis/field/create_value`` route checks that the user can write
  the record.


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
