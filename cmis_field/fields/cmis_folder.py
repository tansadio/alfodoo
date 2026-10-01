# Copyright 2016 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import logging
import time
from functools import partial
from operator import attrgetter

from odoo import SUPERUSER_ID, api, fields
from odoo.exceptions import UserError
from odoo.modules import module
from odoo.modules.registry import Registry

from odoo.addons.cmis.client import CmisObject
from odoo.addons.cmis.exceptions import CMISObjectNotFoundError

_logger = logging.getLogger(__name__)


class CmisFolder(fields.Char):
    """A reference to a cmis:folder. (cmis:objectId)

    The value is stored as a ``varchar``, like a ``Char`` field, and is the
    ``cmis:objectId`` of the folder in the CMIS repository.

    :param backend_name:

        The attribute ``backend_name`` is mandatory if more than one backend
        id configured. Otherwize you must have configured one backend ir order
        to prevent errors when loading a view that includes this kind of field.

    :param allow_create: Allow create from UI (by default True)

    :param allow_delete: Allow delete from UI (by default False)

    :param create_method: name of a method that create the field into the
        CMIS repository. The method must assign the field on all records of the
        invoked recordset. The method is called with the field definition
        instance and the bakend as paramaters
        (optional)

    :param create_parent_get: name of a method that return the cmis:objectId of
        the folder to use as parent. The method is called with the field
        definition instance and the bakend as paramaters.
        (optional: by default the folder is
        created  as child of backend.initial_directory_write + '/' model._name)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: 'cmis:objectId'}

    :param create_name_get: name of a method that return the name of the
        folder to create into the CMIS repository. The method is called with
        the field definition instance and the bakend as paramaters.
        (optional: by default the display_name of the records)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: 'name'}

    :parem create_properties_get: name of a method that return a dictionary of
        CMIS properties ro use to create the folder. The method is called
        with the field definition instance and the bakend as paramaters
        (optional: default empty)
    :rtype: dict
    :return: a dictionay with an entry for each record of the invoked
        recordset with the following structure ::

            {record.id: {'cmis:xxx': 'val1', ...}}

    """

    type = "cmis_folder"
    backend_name = None
    create_method = None
    create_name_get = "display_name"
    create_parent_get = None
    create_properties_get = None
    allow_create = True
    allow_delete = False
    copy = False  # noderef are not copied by default
    trim = False

    # related and inherited fields use the backend of their target field
    _related_backend_name = property(attrgetter("backend_name"))

    def _is_registry_loading_mode(self, env):
        """
        Check if we are in the installation process.
        """
        return env.context.get("install_mode")

    def _description_backend(self, env):
        backend = self.get_backend(env, raise_if_not_found=False)
        if len(backend) > 1:
            if self._is_registry_loading_mode(env):
                # While the registry is loading, specific attributes are not available
                # on the field (such as `backend_name`). At this stage, the fields
                # are accessed to validate the xml views of the module being
                # loaded/updated. We can therefore safely takes the first backend
                # into the list.
                backend = backend[:1]
            else:
                msg = env._("Too many backend found. Please check your configuration.")
                return {"backend_error": msg}
        if not backend:
            if self.backend_name:
                msg = env._(
                    "Backend named %s not found. Please check your configuration.",
                    self.backend_name,
                )
            else:
                msg = env._("No backend found. Please check your configuration.")
            return {"backend_error": msg}
        return backend.get_web_description()[backend.id]

    _description_allow_create = property(attrgetter("allow_create"))
    _description_allow_delete = property(attrgetter("allow_delete"))

    def get_backend(self, env, raise_if_not_found=True):
        return env["cmis.backend"].get_by_name(self.backend_name, raise_if_not_found)

    def create_value(self, records):
        """Create a new folder for each record into the cmis container and
        store the value as field value
        """
        for record in records:
            self._check_null(record)
        if self.related:
            self._create_value_related(records)
        else:
            self._create_value(records)

    def _create_value(self, records):
        backend = self.get_backend(records.env)
        if self.create_method:
            fct = self.create_method
            if not callable(fct):
                fct = getattr(records, fct)
            fct(self, backend)
            return
        self._create_in_cmis(records, backend)

    def _create_value_related(self, records):
        others = records.sudo() if self.compute_sudo else records
        for other in others:
            target, field = self.traverse_related(other)
            field.create_value(target)
        records.invalidate_recordset([self.name])

    def _create_in_cmis(self, records, backend):
        names = self.get_create_names(records, backend)
        parents = self.get_create_parents(records, backend)
        properties = self.get_create_properties(records, backend)
        repo = backend.get_cmis_repository()
        for record in records:
            name = names[record.id]
            if backend.enable_sanitize_cmis_name:
                name = backend.sanitize_cmis_name(name)
            else:
                backend.is_valid_cmis_name(name, raise_if_invalid=True)
            parent = parents[record.id]
            parent_id = parent.id if isinstance(parent, CmisObject) else parent
            name = backend.get_unique_folder_name(name, parent_id)
            props = properties[record.id] or {}
            value = repo.create_folder(parent_id, name, props)

            # remove created resource in case of rollback
            if not module.current_test:
                record.env.cr.postrollback.add(
                    partial(
                        self._clean_up_folder,
                        value.id,
                        backend.id,
                        record.env.cr.dbname,
                    ),
                )

            self.__set__(record, value.id)

    @staticmethod
    def _clean_up_folder(cmis_object_id, backend_id, dbname):
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            backend = env["cmis.backend"].browse(backend_id)
            repo = backend.get_cmis_repository()
            # The rollback is delayed by an arbitrary length of time to give
            # the GED time to create the folder. If the folder is not properly
            # created at the time the rollback executes, it cannot be deleted.
            time.sleep(0.5)
            try:
                repo.get_object(cmis_object_id).delete_tree()
            except CMISObjectNotFoundError:
                _logger.info("Cannot clean up folder %s: not found", cmis_object_id)

    def _check_null(self, record, raise_exception=True):
        val = self.__get__(record, record)
        if val and raise_exception:
            raise UserError(
                record.env._("A value is already assigned to %s", self.string)
            )
        return val

    def get_create_names(self, records, backend):
        """return the names of the folders to create into the CMIS repository
        for the given recordset.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: 'name'}

        """
        if self.create_name_get in ("display_name", "name_get"):
            return {record.id: record.display_name for record in records}
        fct = self.create_name_get
        if not callable(fct):
            fct = getattr(records, fct)
        return fct(self, backend)

    def get_create_parents(self, records, backend):
        """return the cmis:objectId of the cmis folder to use as parent of the
        new folder.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: 'cmis:objectId'}

        """
        if self.create_parent_get:
            fct = self.create_parent_get
            if not callable(fct):
                fct = getattr(records, fct)
            return fct(self, backend)
        path_parts = self.get_default_parent_path_parts(records, backend)
        parent_cmis_object = backend.get_folder_by_path_parts(
            path_parts, create_if_not_found=True
        )
        return dict.fromkeys(records.ids, parent_cmis_object.id)

    def get_create_properties(self, records, backend):
        """Return the properties to use to created the folder into the CMIS
        container.
        :rtype: dict
        :return: a dictionay with an entry for each record with the following
        structure ::

            {record.id: {'cmis:xxx': 'val1', ...}}

        """
        if self.create_properties_get:
            fct = self.create_properties_get
            if not callable(fct):
                fct = getattr(records, fct)
            return fct(self, backend)
        return dict.fromkeys(records.ids, None)

    def get_default_parent_path_parts(self, records, backend):
        """Return the default path parts into the cmis container to use as
        parent on folder create. By default:
        backend.initial_directory_write / record._name
        """
        path_parts = backend.initial_directory_write.split("/")
        path_parts.append(records[0]._name.replace(".", "_"))
        return path_parts

    def get_cmis_object(self, record):
        """Returns the :class:`odoo.addons.cmis.client.CmisObject` of the
        folder, that can be used to perform actions on the folder into the
        cmis container
        :param record:
        """
        val = self.__get__(record, record)
        if not val:
            return None
        backend = self.get_backend(record.env)
        repo = backend.get_cmis_repository()
        return repo.get_object(val)
