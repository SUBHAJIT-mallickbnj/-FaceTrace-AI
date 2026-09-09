import unittest
from unittest.mock import patch

import numpy as np

from pages.helper.db_queries import _create_engine, _normalize_database_url, get_database_path
from pages.helper.utils import (
    detect_all_faces,
    get_login_config_path,
    get_project_root,
    get_resources_dir,
)


class ProjectPathTests(unittest.TestCase):
    def test_postgres_engine_disables_prepared_statements_at_driver_level(self):
        with patch("pages.helper.db_queries.create_engine") as create_engine:
            _create_engine("postgresql+psycopg://user:password@host/db")

        options = create_engine.call_args.kwargs
        self.assertEqual(options["connect_args"]["prepare_threshold"], 0)

    def test_supabase_pooler_uses_transaction_mode_for_streamlit(self):
        url = _normalize_database_url(
            "postgresql://user:password@aws-0-region.pooler.supabase.com:5432/db"
        )

        self.assertIn("@aws-0-region.pooler.supabase.com:6543/", url)
        self.assertIn("prepare_threshold=0", url)

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

    def test_opencv_fallback_runs_when_mediapipe_native_library_fails(self):
        fallback_face = {
            "bbox": (1, 2, 30, 40),
            "embedding": [0.1, 0.2],
        }
        with patch("pages.helper.utils._ensure_model"), patch(
            "pages.helper.utils._build_detector",
            side_effect=OSError("libGLESv2.so.2: cannot open shared object file"),
        ), patch(
            "pages.helper.utils._detect_identity_faces",
            return_value=[fallback_face],
        ):
            faces = detect_all_faces(np.zeros((50, 50, 3), dtype=np.uint8))

        self.assertEqual(faces, [
            {"landmarks": [], "bbox": (1, 2, 30, 40), "embedding": [0.1, 0.2]}
        ])


if __name__ == "__main__":
    unittest.main()
