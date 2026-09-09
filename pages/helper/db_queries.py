import sqlite3
import uuid
import os
import base64
import threading
import time
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool
from sqlmodel import create_engine, Session, select
import streamlit as st

from pages.helper.data_models import RegisteredCases, PublicSubmissions
from pages.helper.utils import get_database_path, get_resources_dir
from pages.helper.map_utils import geocode_last_seen_location, geocode_location
from pages.helper.map_utils import normalize_location
from pages.helper import image_store

def _get_configured_database_url() -> str | None:
    try:
        password = st.secrets.get("SUPABASE_DB_PASSWORD")
        project_ref = st.secrets.get(
            "SUPABASE_PROJECT_REF", "juimizsbqheuvxfphutx"
        )
        region = st.secrets.get("SUPABASE_REGION", "ap-northeast-1")
        if password:
            return _normalize_database_url(
                "postgresql://"
                f"postgres.{project_ref}:{quote(str(password), safe='')}@"
                f"aws-0-{region}.pooler.supabase.com:6543/postgres"
            )
        configured_url = st.secrets.get("DATABASE_URL")
    except Exception:
        configured_url = None
    configured_url = configured_url or os.getenv("DATABASE_URL")
    if configured_url:
        return _normalize_database_url(str(configured_url))
    return None


def _get_database_url() -> str:
    """Use the configured shared database, with SQLite only for local development."""
    configured_url = _get_configured_database_url()
    if configured_url:
        return configured_url
    return f"sqlite:///{get_database_path().resolve().as_posix()}"


def _normalize_database_url(configured_url: str) -> str:
    """Normalize PostgreSQL URLs for psycopg and serverless Streamlit apps."""
    configured_url = configured_url.strip().strip('"').strip("'")
    if configured_url.startswith("postgres://"):
        configured_url = configured_url.replace("postgres://", "postgresql://", 1)
    if not configured_url.startswith("postgresql"):
        return configured_url
    if configured_url.startswith("postgresql://"):
        configured_url = configured_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    parsed = urlsplit(configured_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if parsed.hostname and parsed.hostname.endswith("pooler.supabase.com"):
        # Supabase 5432 is session pooling with a small per-project client cap.
        # Streamlit creates short-lived connections across multiple app workers,
        # so use transaction pooling instead.
        if parsed.port == 5432:
            parsed = parsed._replace(netloc=parsed.netloc.rsplit(":", 1)[0] + ":6543")
        query.setdefault("prepare_threshold", "0")
    query.setdefault("sslmode", "require")
    query.setdefault("connect_timeout", "10")
    return urlunsplit(parsed._replace(query=urlencode(query)))


def _create_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {
        # Supabase transaction poolers do not support prepared statements.
        "prepare_threshold": 0,
    }
    options = {
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if not url.startswith("sqlite"):
        options["poolclass"] = NullPool
    return create_engine(url, **options)


database_url = _get_database_url()
engine = _create_engine(database_url)
_database_init_lock = threading.Lock()
_initialized_engine_id = None


def _database_failure_detail(exc: Exception) -> str:
    messages = []
    current = exc
    while current is not None:
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    message = " ".join(messages)
    if "max clients" in message or "too many connections" in message:
        return "Supabase connection limit reached; transaction pooling is required."
    if "password authentication failed" in message or "authentication failed" in message:
        return "PostgreSQL authentication failed; verify DATABASE_URL credentials."
    if "could not translate host name" in message or "name or service not known" in message:
        return "DATABASE_URL hostname could not be resolved."
    if "timeout" in message or "timed out" in message:
        return "Supabase connection timed out; verify the pooler host and port 6543."
    if "ssl" in message or "certificate" in message:
        return "Supabase SSL negotiation failed; DATABASE_URL must use sslmode=require."
    if "port" in message and "6543" in message:
        return "Supabase pooler port 6543 is unavailable; verify the project pooler is enabled."
    return "Check DATABASE_URL format, Supabase project status, and Streamlit secrets."


def create_db():
    """Initialize the active database once per process and engine instance."""
    global database_url, engine, _initialized_engine_id
    engine_id = id(engine)
    if _initialized_engine_id == engine_id:
        return

    with _database_init_lock:
        if _initialized_engine_id == engine_id:
            return
        last_error = None
        for attempt in range(3):
            try:
                with engine.begin() as connection:
                    connection.execute(text("SELECT 1"))
                    RegisteredCases.__table__.create(connection, checkfirst=True)
                    PublicSubmissions.__table__.create(connection, checkfirst=True)
                break
            except SQLAlchemyError as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt)
        else:
            if not database_url.startswith("sqlite"):
                detail = _database_failure_detail(last_error)
                raise RuntimeError(
                    "The configured DATABASE_URL is unavailable after 3 attempts. "
                    f"{detail} Both Streamlit apps must use the same working "
                    "PostgreSQL secret; SQLite fallback is disabled."
                ) from last_error
            raise last_error
        # Add new columns to existing databases without dropping data.
        _migrate_db()
        _backfill_image_data()
        _initialized_engine_id = engine_id


def _migrate_db():
    """Add new columns to an existing database without dropping data."""
    new_columns = [
        ("registeredcases", "complainant_email", "TEXT"),
        ("registeredcases", "city", "TEXT"),
        ("registeredcases", "description", "TEXT"),
        ("registeredcases", "pincode", "TEXT"),
        ("registeredcases", "latitude", "REAL"),
        ("registeredcases", "longitude", "REAL"),
        ("publicsubmissions", "image_data", "TEXT"),
        ("registeredcases", "image_data", "TEXT"),
    ]
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, column, col_type in new_columns:
            if table not in inspector.get_table_names():
                continue
            existing_columns = {item["name"] for item in inspector.get_columns(table)}
            if column not in existing_columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def _backfill_image_data():
    """Copy still-available local images into durable database storage once."""
    resources_dir = get_resources_dir()
    with Session(engine) as session:
        registered_rows = session.exec(
            select(RegisteredCases.id).where(RegisteredCases.image_data.is_(None))
        ).all()
        public_rows = session.exec(
            select(PublicSubmissions.id).where(PublicSubmissions.image_data.is_(None))
        ).all()
        for model, rows in (
            (RegisteredCases, registered_rows),
            (PublicSubmissions, public_rows),
        ):
            for case_id in rows:
                image_path = resources_dir / f"{case_id}.jpg"
                if not image_path.exists():
                    continue
                image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
                record = session.get(model, str(case_id))
                if record is not None:
                    record.image_data = image_data
                    image_store.backup_image(str(case_id), image_path.read_bytes())
                    _backup_case_data(
                        record,
                        "registered" if model is RegisteredCases else "public",
                    )
        session.commit()


def _case_backup_data(case) -> dict:
    """Return serializable case metadata without duplicating the image blob."""
    data = case.model_dump() if hasattr(case, "model_dump") else case.dict()
    data.pop("image_data", None)
    return data


def _backup_case_data(case, case_type: str):
    if not image_store.backup_case_data(case_type, str(case.id), _case_backup_data(case)):
        print(f"[WARNING] Case saved to PostgreSQL but not Google Drive: {case.id}")


def register_new_case(case_details: RegisteredCases):
    with Session(engine) as session:
        try:
            session.add(case_details)
            session.commit()
            session.refresh(case_details)
        except (sqlite3.IntegrityError, SQLAlchemyIntegrityError):
            session.rollback()
            case_details.id = str(uuid.uuid4())
            session.add(case_details)
            session.commit()
            session.refresh(case_details)
        except Exception:
            session.rollback()
            raise
    _backup_case_data(case_details, "registered")


def set_registered_case_image(case_id: str, image_data):
    """Persist a registered-case image as base64 in the shared database."""
    if isinstance(image_data, (bytes, bytearray, memoryview)):
        image_bytes = bytes(image_data)
        image_data = base64.b64encode(image_bytes).decode("ascii")
    elif image_data:
        image_data = str(image_data)
        image_bytes = _decode_image_data(image_data)
    else:
        image_bytes = None
    with Session(engine) as session:
        case = session.get(RegisteredCases, str(case_id))
        if case is None:
            raise ValueError(f"Registered case not found: {case_id}")
        case.image_data = image_data
        session.add(case)
        session.commit()
        session.refresh(case)
    _backup_case_data(case, "registered")
    if image_bytes:
        if not image_store.backup_image(str(case_id), image_bytes):
            detail = image_store.last_error() or "Drive credentials or folder access is not configured."
            print(f"[WARNING] Registered image saved to PostgreSQL but not Google Drive: {detail}")
            st.warning(f"Image saved to PostgreSQL, but Google Drive backup failed: {detail}")


def get_registered_case_image(case_id: str) -> bytes | None:
    """Return a registered-case image from durable database storage."""
    with Session(engine) as session:
        image_data = session.exec(
            select(RegisteredCases.image_data).where(RegisteredCases.id == str(case_id))
        ).first()
    if not image_data:
        restored = image_store.restore_image(str(case_id))
        if restored:
            set_registered_case_image(case_id, restored)
        return restored
    if isinstance(image_data, (bytes, bytearray, memoryview)):
        return bytes(image_data)
    if isinstance(image_data, str) and image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[-1]
    try:
        decoded = base64.b64decode(str(image_data).strip(), validate=True)
        image_store.backup_image(str(case_id), decoded)
        return decoded
    except (TypeError, ValueError, base64.binascii.Error):
        restored = image_store.restore_image(str(case_id))
        if restored:
            set_registered_case_image(case_id, restored)
        return restored


def _decode_image_data(image_data: str) -> bytes | None:
    if image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[-1]
    try:
        return base64.b64decode(image_data.strip(), validate=True)
    except (TypeError, ValueError, base64.binascii.Error):
        return None


def fetch_registered_cases(submitted_by: str, status: str):
    print(f"submitted_by: {submitted_by}")
    if status == "All":
        status = ["F", "NF"]
    elif status == "Found":
        status = ["F"]
    elif status == "Not Found":
        status = ["NF"]
    else:
        status = ["F", "NF"]  # Default to both statuses

    with Session(engine) as session:
        result = session.exec(
            select(
                RegisteredCases.id,
                RegisteredCases.name,
                RegisteredCases.age,
                RegisteredCases.status,
                RegisteredCases.last_seen,
                RegisteredCases.matched_with,
            )
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status.in_(status))
        ).all()
        return result


def fetch_public_cases(train_data: bool, status: str = None):
    if train_data:
        with Session(engine) as session:
            # Build query based on status parameter
            q = select(
                PublicSubmissions.id,
                PublicSubmissions.face_mesh,
            )
            
            # Only apply status filter if provided
            if status is not None:
                q = q.where(PublicSubmissions.status == status)
            
            result = session.exec(q).all()
            return result

    with Session(engine) as session:
        result = session.exec(
            select(
                PublicSubmissions.id,
                PublicSubmissions.status,
                PublicSubmissions.location,
                PublicSubmissions.mobile,
                PublicSubmissions.birth_marks,
                PublicSubmissions.submitted_on,
                PublicSubmissions.submitted_by,
            )
        ).all()
        return result


def get_not_confirmed_registered_cases(submitted_by: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == "NF")
        ).all()
        return result


def get_training_data(submitted_by: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases.id, RegisteredCases.face_mesh)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == "NF")
        ).all()
        return result


def new_public_case(public_case_details: PublicSubmissions):
    if public_case_details.image_data:
        if isinstance(public_case_details.image_data, bytes):
            public_case_details.image_data = base64.b64encode(
                public_case_details.image_data
            ).decode("ascii")
        else:
            public_case_details.image_data = str(public_case_details.image_data)

    image_bytes = _decode_image_data(public_case_details.image_data) if public_case_details.image_data else None
    with Session(engine) as session:
        session.add(public_case_details)
        session.commit()
        session.refresh(public_case_details)
    _backup_case_data(public_case_details, "public")
    if image_bytes:
        if not image_store.backup_image(str(public_case_details.id), image_bytes):
            detail = image_store.last_error() or "Drive credentials or folder access is not configured."
            print(f"[WARNING] Public image saved to PostgreSQL but not Google Drive: {detail}")
            st.warning(f"Image saved to PostgreSQL, but Google Drive backup failed: {detail}")


def auto_confirm_public_matches():
    """Confirm new high-confidence public sightings without duplicate updates."""
    from pages.helper import match_algo

    matches = match_algo.match()
    if not matches.get("status"):
        return []

    confirmed = []
    for registered_id, submissions in matches.get("result", {}).items():
        for submission in submissions:
            public_id = submission[0] if isinstance(submission, tuple) else submission
            update_found_status(registered_id, public_id)
            confirmed.append((registered_id, public_id))
    return confirmed


def get_public_case_detail(case_id: str):
    with Session(engine) as session:
        result = session.exec(
            select(
                PublicSubmissions.location,
                PublicSubmissions.submitted_by,
                PublicSubmissions.mobile,
                PublicSubmissions.birth_marks,
            ).where(PublicSubmissions.id == case_id)
        ).all()
        return result


def get_public_case_image(case_id: str) -> bytes | None:
    """Return shared public-upload image bytes from the hosted database."""
    with Session(engine) as session:
        image_data = session.exec(
            select(PublicSubmissions.image_data).where(PublicSubmissions.id == case_id)
        ).first()
    if not image_data:
        restored = image_store.restore_image(str(case_id))
        if restored:
            _restore_public_case_image(case_id, restored)
        return restored

    if isinstance(image_data, (bytes, bytearray, memoryview)):
        return bytes(image_data)

    if isinstance(image_data, str) and image_data.startswith("data:"):
        image_data = image_data.split(",", 1)[-1]

    try:
        decoded = base64.b64decode(str(image_data).strip(), validate=True)
        image_store.backup_image(str(case_id), decoded)
        return decoded
    except (TypeError, ValueError, base64.binascii.Error):
        restored = image_store.restore_image(str(case_id))
        if restored:
            _restore_public_case_image(case_id, restored)
        return restored


def _restore_public_case_image(case_id: str, image_bytes: bytes):
    with Session(engine) as session:
        case = session.get(PublicSubmissions, str(case_id))
        if case is not None:
            case.image_data = base64.b64encode(image_bytes).decode("ascii")
            session.add(case)
            session.commit()


def get_registered_case_id_for_public_case(public_case_id: str) -> str | None:
    """Return the registered case linked to a confirmed public sighting."""
    with Session(engine) as session:
        return session.exec(
            select(RegisteredCases.id)
            .where(RegisteredCases.matched_with == public_case_id)
        ).first()


def get_registered_case_detail(case_id: str):
    with Session(engine) as session:
        result = session.exec(
            select(
                RegisteredCases.name,
                RegisteredCases.complainant_mobile,
                RegisteredCases.complainant_email,
                RegisteredCases.age,
                RegisteredCases.last_seen,
                RegisteredCases.birth_marks,
            ).where(RegisteredCases.id == case_id)
        ).all()
        return result


def get_confirmed_matches(submitted_by: str):
    """Return found registered cases and their public response details."""
    with Session(engine) as session:
        rows = session.exec(
            select(
                RegisteredCases.id,
                RegisteredCases.name,
                RegisteredCases.age,
                RegisteredCases.last_seen,
                RegisteredCases.matched_with,
                PublicSubmissions.id,
                PublicSubmissions.location,
                PublicSubmissions.submitted_by,
                PublicSubmissions.mobile,
                PublicSubmissions.birth_marks,
                PublicSubmissions.submitted_on,
            )
            .join(
                PublicSubmissions,
                RegisteredCases.matched_with == PublicSubmissions.id,
            )
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == "F")
        ).all()
    return rows


def list_public_cases():
    with Session(engine) as session:
        result = session.exec(select(PublicSubmissions)).all()
        return result


def update_found_status(register_case_id: str, public_case_id: str):
    with Session(engine) as session:
        registered_case_details = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == str(register_case_id))
        ).one()
        registered_case_details.status = "F"
        registered_case_details.matched_with = str(public_case_id)

        public_case_details = session.exec(
            select(PublicSubmissions).where(PublicSubmissions.id == str(public_case_id))
        ).one()
        public_case_details.status = "F"

        session.add(registered_case_details)
        session.add(public_case_details)
        session.commit()
        session.refresh(registered_case_details)
        session.refresh(public_case_details)
    _backup_case_data(registered_case_details, "registered")
    _backup_case_data(public_case_details, "public")


def get_registered_cases_count(submitted_by: str, status: str):
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases)
            .where(RegisteredCases.submitted_by == submitted_by)
            .where(RegisteredCases.status == status)
        ).all()
        return result


def get_case_counts_by_city():
    """Return live status counts grouped by the best known city."""
    with Session(engine) as session:
        result = session.exec(
            select(RegisteredCases.city, RegisteredCases.last_seen, RegisteredCases.status)
        ).all()
    counts = {}
    for city, last_seen, status in result:
        city = normalize_location(city or last_seen)
        if city not in counts:
            counts[city] = {"found": 0, "not_found": 0}
        if status == "F":
            counts[city]["found"] += 1
        else:
            counts[city]["not_found"] += 1
    return counts


def get_cases_for_map():
    """Return every registered case so the map reflects each case's live status."""
    with Session(engine) as session:
        return session.exec(
            select(
                RegisteredCases.id,
                RegisteredCases.name,
                RegisteredCases.status,
                RegisteredCases.city,
                RegisteredCases.last_seen,
                RegisteredCases.address,
                RegisteredCases.latitude,
                RegisteredCases.longitude,
            )
        ).all()


def delete_registered_case(case_id: str):
    with Session(engine) as session:
        case = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == case_id)
        ).one()
        session.delete(case)
        session.commit()
    # Remove image from disk
    image_path = get_resources_dir() / f"{case_id}.jpg"
    if image_path.exists():
        image_path.unlink()


def update_registered_case(case_id: str, fields: dict):
    with Session(engine) as session:
        case = session.exec(
            select(RegisteredCases).where(RegisteredCases.id == case_id)
        ).one()
        for key, value in fields.items():
            setattr(case, key, value)
        if any(key in fields for key in ("address", "pincode", "last_seen", "city")):
            # An edited Last Seen value is authoritative; do not let stale
            # registration fields pull the marker back to the old location.
            if "last_seen" in fields:
                case.latitude, case.longitude = geocode_last_seen_location(case.last_seen)
            else:
                case.latitude, case.longitude = geocode_location(
                    case.city,
                    case.last_seen,
                    case.address,
                    case.pincode,
                )
        session.add(case)
        session.commit()
        session.refresh(case)
    _backup_case_data(case, "registered")


if __name__ == "__main__":
    r = fetch_public_cases("NF")
    print(r)
