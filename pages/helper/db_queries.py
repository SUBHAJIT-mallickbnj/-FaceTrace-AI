import sqlite3
import uuid
import os
import base64
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.exc import IntegrityError as SQLAlchemyIntegrityError
from sqlalchemy import inspect, text
from sqlalchemy.pool import NullPool
from sqlmodel import create_engine, Session, select
import streamlit as st

from pages.helper.data_models import RegisteredCases, PublicSubmissions
from pages.helper.utils import get_database_path, get_resources_dir
from pages.helper.map_utils import normalize_location

def _get_database_url() -> str:
    """Use one hosted database in Cloud, with local SQLite as the fallback."""
    try:
        configured_url = st.secrets.get("DATABASE_URL")
    except Exception:
        configured_url = None
    configured_url = configured_url or os.getenv("DATABASE_URL")
    if configured_url:
        return _normalize_database_url(str(configured_url))
    return f"sqlite:///{get_database_path().resolve().as_posix()}"


def _normalize_database_url(configured_url: str) -> str:
    """Normalize managed PostgreSQL URLs for psycopg and Streamlit Cloud."""
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
    query.setdefault("sslmode", "require")
    query.setdefault("connect_timeout", "10")
    return urlunsplit(parsed._replace(query=urlencode(query)))


database_url = _get_database_url()
engine_options = {
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False}
    if database_url.startswith("sqlite")
    else {},
}
if not database_url.startswith("sqlite"):
    engine_options["poolclass"] = NullPool
engine = create_engine(database_url, **engine_options)


def create_db():
    RegisteredCases.__table__.create(engine, checkfirst=True)
    PublicSubmissions.__table__.create(engine, checkfirst=True)
    # Add new columns to existing tables if they don't exist (SQLite migration)
    _migrate_db()


def _migrate_db():
    """Add new columns to an existing database without dropping data."""
    new_columns = [
        ("registeredcases", "complainant_email", "TEXT"),
        ("registeredcases", "city", "TEXT"),
        ("registeredcases", "description", "TEXT"),
        ("registeredcases", "latitude", "REAL"),
        ("registeredcases", "longitude", "REAL"),
        ("publicsubmissions", "image_data", "TEXT"),
    ]
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, column, col_type in new_columns:
            if table not in inspector.get_table_names():
                continue
            existing_columns = {item["name"] for item in inspector.get_columns(table)}
            if column not in existing_columns:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


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
    with Session(engine) as session:
        session.add(public_case_details)
        session.commit()


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
    """Return shared public-upload image bytes, with invalid data treated as missing."""
    with Session(engine) as session:
        image_data = session.exec(
            select(PublicSubmissions.image_data).where(PublicSubmissions.id == case_id)
        ).first()
    if not image_data:
        return None
    try:
        return base64.b64decode(image_data, validate=True)
    except (TypeError, ValueError):
        return None


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
        session.add(case)
        session.commit()


if __name__ == "__main__":
    r = fetch_public_cases("NF")
    print(r)
