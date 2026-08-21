import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlmodel import SQLModel, create_engine

from pages.helper import db_queries
from pages.helper.data_models import PublicSubmissions


def test_public_submission_image_bytes_are_shared_with_admin_views():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        image_bytes = b"fake-jpeg-bytes"
        submission = PublicSubmissions(
            id="public-image-id",
            submitted_by="reporter",
            face_mesh="[1, 2, 3]",
            location="Delhi",
            mobile="1234567890",
            status="NF",
            image_data=base64.b64encode(image_bytes).decode("ascii"),
        )

        with patch.object(db_queries, "engine", temp_engine):
            db_queries.new_public_case(submission)
            assert db_queries.get_public_case_image("public-image-id") == image_bytes

        temp_engine.dispose()