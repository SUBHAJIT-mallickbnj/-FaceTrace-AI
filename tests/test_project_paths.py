import unittest

from pages.helper.db_queries import get_database_path
from pages.helper.utils import get_login_config_path, get_project_root, get_resources_dir


class ProjectPathTests(unittest.TestCase):
    def test_project_root_points_to_repo_root(self):
        root = get_project_root()
        self.assertTrue((root / "Home.py").exists())
        self.assertTrue((root / "login_config.yml").exists())

    def test_database_and_resource_paths_are_project_relative(self):
        root = get_project_root()
        db_path = get_database_path()
        resources_dir = get_resources_dir()
        login_config_path = get_login_config_path()

        self.assertTrue(db_path.is_absolute())
        self.assertTrue(resources_dir.is_absolute())
        self.assertTrue(login_config_path.is_absolute())
        self.assertTrue(str(db_path).startswith(str(root)))
        self.assertTrue(str(resources_dir).startswith(str(root)))
        self.assertTrue(str(login_config_path).startswith(str(root)))


if __name__ == "__main__":
    unittest.main()
