import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlmodel import SQLModel, create_engine

from pages.helper import db_queries
from pages.helper.data_models import PublicSubmissions, RegisteredCases


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


def test_legacy_public_submission_resolves_confirmed_registered_case():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        registered = RegisteredCases(
            id="registered-case-id",
            submitted_by="admin",
            name="Missing Person",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Delhi",
            face_mesh="[1, 2, 3]",
            status="F",
            birth_marks="",
            matched_with="legacy-public-id",
        )
        public = PublicSubmissions(
            id="legacy-public-id",
            submitted_by="reporter",
            face_mesh="[1, 2, 3]",
            location="Delhi",
            mobile="1234567890",
            status="F",
        )

        with patch.object(db_queries, "engine", temp_engine):
            with db_queries.Session(temp_engine) as session:
                session.add(registered)
                session.add(public)
                session.commit()
            assert (
                db_queries.get_registered_case_id_for_public_case("legacy-public-id")
                == "registered-case-id"
            )

        temp_engine.dispose()


def test_public_submission_accepts_raw_bytes_and_data_urls():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)

        raw_submission = PublicSubmissions(
            id="raw-image-id",
            submitted_by="reporter",
            face_mesh="[1, 2, 3]",
            location="Delhi",
            mobile="1234567890",
            status="NF",
            image_data=b"raw-image-bytes",
        )
        data_url_submission = PublicSubmissions(
            id="data-url-image-id",
            submitted_by="reporter",
            face_mesh="[1, 2, 3]",
            location="Delhi",
            mobile="1234567890",
            status="NF",
            image_data=(
                "data:image/jpeg;base64,"
                + base64.b64encode(b"data-url-bytes").decode("ascii")
            ),
        )

        with patch.object(db_queries, "engine", temp_engine):
            db_queries.new_public_case(raw_submission)
            db_queries.new_public_case(data_url_submission)
            assert (
                db_queries.get_public_case_image("raw-image-id")
                == b"raw-image-bytes"
            )
            assert (
                db_queries.get_public_case_image("data-url-image-id")
                == b"data-url-bytes"
            )

        temp_engine.dispose()