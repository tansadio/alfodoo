# © 2014-2015 Savoir-faire Linux (<http://www.savoirfairelinux.com>).
# Copyright 2016 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from unittest import mock

from odoo.exceptions import UserError, ValidationError
from odoo.tests import common

from odoo.addons.cmis.client import CmisPage


class TestCmisBackend(common.TransactionCase):
    def setUp(self):
        super().setUp()
        self.cmis_backend = self.env["cmis.backend"]
        self.backend_instance = self.env.ref("cmis.cmis_backend_alfresco")

    def test_get_by_name(self):
        backend = self.cmis_backend.get_by_name(name=self.backend_instance.name)
        self.assertEqual(self.backend_instance, backend)
        with self.assertRaises(UserError):
            self.cmis_backend.get_by_name("error")
        backend = self.cmis_backend.get_by_name("error", raise_if_not_found=False)
        self.assertFalse(backend)

    def test_is_valid_cmis_name(self):
        backend = self.cmis_backend.get_by_name(name=self.backend_instance.name)
        self.assertFalse(backend.is_valid_cmis_name(r'my\/:*?"<>| directory'))
        self.assertFalse(backend.is_valid_cmis_name(r"abc."))
        self.assertFalse(backend.is_valid_cmis_name(r"abc "))
        self.assertTrue(backend.is_valid_cmis_name("my directory"))
        with self.assertRaises(UserError):
            backend.is_valid_cmis_name(r'my\/:*?"<>| directory', raise_if_invalid=True)

    def test_sanitize_cmis_name(self):
        self.backend_instance.sanitize_replace_char = "_"
        sanitized = self.backend_instance.sanitize_cmis_name("m/y dir*", "_")
        self.assertEqual(sanitized, "m_y dir_")
        sanitized = self.backend_instance.sanitize_cmis_name("m/y dir*", None)
        self.assertEqual(sanitized, "m_y dir_")
        sanitized = self.backend_instance.sanitize_cmis_name("m/y dir*", "")
        self.assertEqual(sanitized, "my dir")
        sanitized = self.backend_instance.sanitize_cmis_name("m/y dir*", "-")
        self.assertEqual(sanitized, "m-y dir-")
        sanitized = self.backend_instance.sanitize_cmis_name("/y dir*", " ")
        self.assertEqual(sanitized, "y dir")
        sanitized = self.backend_instance.sanitize_cmis_name("xyz.", " ")
        self.assertEqual(sanitized, "xyz")
        sanitized = self.backend_instance.sanitize_cmis_name("xyz.....", " ")
        self.assertEqual(sanitized, "xyz")
        sanitized = self.backend_instance.sanitize_cmis_name(".x.y.z..", " ")
        self.assertEqual(sanitized, ".x.y.z")
        with self.assertRaises(ValidationError):
            self.backend_instance.sanitize_replace_char = "/"

        sanitized = self.backend_instance.sanitize_cmis_names(
            ["/y dir*", "sub/dir"], " "
        )
        self.assertEqual(sanitized, ["y dir", "sub dir"])

    @staticmethod
    def _folder(name):
        folder = mock.MagicMock()
        folder.name = name
        return folder

    def _mock_query(self, *pages):
        """Patch the repository to answer the queries with the given pages
        of folder names"""
        repository = mock.MagicMock()
        repository.query.side_effect = [
            CmisPage([self._folder(name) for name in names], False, len(names))
            for names in pages
        ]
        patcher = mock.patch.object(
            type(self.backend_instance), "get_cmis_repository", return_value=repository
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return repository

    def test_get_unique_folder_name(self):
        # if no name found, the method return the same name
        self._mock_query([])
        self.assertEqual(
            "test", self.backend_instance.get_unique_folder_name("test", "parent_id")
        )

    def test_get_unique_folder_name_error(self):
        # if the same name is found and the folder_name_conflict_handler ==
        # 'error' a ValidationError is raised
        self._mock_query(["test"])
        self.backend_instance.folder_name_conflict_handler = "error"
        with self.assertRaises(ValidationError):
            self.backend_instance.get_unique_folder_name("test", "parent_id")

    def test_get_unique_folder_name_increment(self):
        # if the same name is found and the folder_name_conflict_handler ==
        # 'increment' the method must return a new name with a suffix _(X)
        # where X is the value max found as X for the same name + 1
        repository = self._mock_query(
            ["test"], ["test_(backup)", "test_(1)", "test_(3)"]
        )
        self.backend_instance.folder_name_conflict_handler = "increment"
        parent = mock.MagicMock(id="parent_id")
        name = self.backend_instance.get_unique_folder_name("test", parent)
        self.assertEqual("test_(4)", name)
        query = repository.query.call_args_list[1][0][0]
        self.assertIn("IN_FOLDER('parent_id')", query)
        self.assertIn("cmis:name LIKE 'test\\_(%)'", query)

    def test_get_unique_folder_name_increment_first(self):
        # in this case a name is found put without increment
        self._mock_query(["test"], ["test_(backup)"])
        self.backend_instance.folder_name_conflict_handler = "increment"
        name = self.backend_instance.get_unique_folder_name("test", "parent_id")
        self.assertEqual("test_(1)", name)

    def test_get_unique_folder_name_quote(self):
        repository = self._mock_query([])
        self.backend_instance.get_unique_folder_name("l'été", "parent_id")
        query = repository.query.call_args[0][0]
        self.assertIn("cmis:name='l\\'été'", query)
