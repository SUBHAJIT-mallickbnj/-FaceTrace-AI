import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
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


def test_registered_case_image_is_persisted_and_retrieved():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        registered = RegisteredCases(
            id="registered-image-id",
            submitted_by="admin",
            name="Missing Person",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Delhi",
            face_mesh="[1, 2, 3]",
            status="NF",
            birth_marks="",
        )

        with patch.object(db_queries, "engine", temp_engine):
            db_queries.register_new_case(registered)
            db_queries.set_registered_case_image(
                "registered-image-id", b"registered-jpeg-bytes"
            )
            assert (
                db_queries.get_registered_case_image("registered-image-id")
                == b"registered-jpeg-bytes"
            )

        temp_engine.dispose()


def test_existing_local_registered_image_is_backfilled_to_database():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        resources_dir = Path(tmpdir) / "resources"
        resources_dir.mkdir()
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        registered = RegisteredCases(
            id="legacy-registered-image-id",
            submitted_by="admin",
            name="Missing Person",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Delhi",
            face_mesh="[1, 2, 3]",
            status="NF",
            birth_marks="",
        )
        with db_queries.Session(temp_engine) as session:
            session.add(registered)
            session.commit()
        (resources_dir / "legacy-registered-image-id.jpg").write_bytes(
            b"legacy-jpeg-bytes"
        )

        with patch.object(db_queries, "engine", temp_engine), patch.object(
            db_queries, "get_resources_dir", return_value=resources_dir
        ):
            db_queries._backfill_image_data()
            assert (
                db_queries.get_registered_case_image("legacy-registered-image-id")
                == b"legacy-jpeg-bytes"
            )

        temp_engine.dispose()


def test_configured_database_failure_does_not_fallback_to_sqlite():
    class FailingEngine:
        def connect(self):
            raise SQLAlchemyError("database unavailable")

    original_engine = db_queries.engine
    original_url = db_queries.database_url
    try:
        db_queries.engine = FailingEngine()
        db_queries.database_url = "postgresql+psycopg://configured-host/db"
        with pytest.raises(RuntimeError, match="SQLite fallback is disabled"):
            db_queries.create_db()
        assert db_queries.database_url.startswith("postgresql")
    finally:
        db_queries.engine = original_engine
        db_queries.database_url = original_url


def test_public_submission_auto_confirms_matching_registered_case():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        embedding = [1.0, 0.0] + [0.0] * 126
        registered = RegisteredCases(
            id="matching-case-id",
            submitted_by="admin",
            name="Missing Person",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Delhi",
            face_mesh=json.dumps(embedding),
            status="NF",
            birth_marks="",
        )
        public = PublicSubmissions(
            id="matching-sighting-id",
            submitted_by="reporter",
            face_mesh=json.dumps(embedding),
            location="Delhi",
            mobile="9876543210",
            status="NF",
            image_data=base64.b64encode(b"photo").decode("ascii"),
        )

        with patch.object(db_queries, "engine", temp_engine):
            db_queries.register_new_case(registered)
            db_queries.new_public_case(public)
            assert db_queries.auto_confirm_public_matches() == [
                ("matching-case-id", "matching-sighting-id")
            ]
            with db_queries.Session(temp_engine) as session:
                saved_registered = session.get(RegisteredCases, "matching-case-id")
                saved_public = session.get(PublicSubmissions, "matching-sighting-id")
                assert saved_registered.status == "F"
                assert saved_registered.matched_with == "matching-sighting-id"
                assert saved_public.status == "F"

        temp_engine.dispose()


def test_editing_last_seen_recalculates_registered_case_coordinates():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        registered = RegisteredCases(
            id="editable-map-case",
            submitted_by="admin",
            name="Map Test",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Connaught Place",
            pincode="110001",
            city="Delhi",
            face_mesh="[]",
            status="NF",
            birth_marks="",
        )

        with patch.object(db_queries, "engine", temp_engine), patch(
            "pages.helper.db_queries.geocode_location",
            return_value=(34.0837, 74.7973),
        ) as geocode:
            db_queries.register_new_case(registered)
            db_queries.update_registered_case(
                "editable-map-case",
                {"last_seen": "Srinagar, Kashmir", "pincode": "190001"},
            )
            with db_queries.Session(temp_engine) as session:
                saved = session.get(RegisteredCases, "editable-map-case")
                assert saved.last_seen == "Srinagar, Kashmir"
                assert saved.latitude == 34.0837
                assert saved.longitude == 74.7973
            geocode.assert_called_with(
                "Delhi", "Srinagar, Kashmir", "Connaught Place", "190001"
            )

        temp_engine.dispose()


def test_editing_last_seen_ignores_stale_registration_location_fields():
    with TemporaryDirectory() as tmpdir:
        temp_db = Path(tmpdir) / "test.db"
        temp_engine = create_engine(f"sqlite:///{temp_db}")
        SQLModel.metadata.create_all(temp_engine)
        registered = RegisteredCases(
            id="stale-location-case",
            submitted_by="admin",
            name="Stale Location Test",
            complainant_name="Family",
            complainant_mobile="1234567890",
            adhaar_card="123456789012",
            last_seen="Delhi",
            address="Old Delhi address",
            pincode="110001",
            city="Delhi",
            face_mesh="[]",
            status="NF",
            birth_marks="",
        )

        with patch.object(db_queries, "engine", temp_engine), patch(
            "pages.helper.db_queries.geocode_location",
            return_value=(34.0837, 74.7973),
        ) as geocode:
            db_queries.register_new_case(registered)
            db_queries.update_registered_case(
                "stale-location-case",
                {"last_seen": "Srinagar, Lal Chowk, 190001"},
            )
            with db_queries.Session(temp_engine) as session:
                saved = session.get(RegisteredCases, "stale-location-case")
                assert (saved.latitude, saved.longitude) == (34.0837, 74.7973)
            geocode.assert_called_with(None, "Srinagar, Lal Chowk, 190001", None, None)

        temp_engine.dispose()