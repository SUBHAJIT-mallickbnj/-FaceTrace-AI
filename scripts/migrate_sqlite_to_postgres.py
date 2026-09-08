"""Copy legacy SQLite records into the configured PostgreSQL database."""

import base64
import os
import sys
from pathlib import Path

from sqlmodel import Session, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pages.helper import db_queries, image_store
from pages.helper.data_models import PublicSubmissions, RegisteredCases


def _image_bytes(value) -> bytes | None:
    if not value:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    try:
        return base64.b64decode(str(value).split(",", 1)[-1], validate=True)
    except (TypeError, ValueError, base64.binascii.Error):
        return None


def _copy_table(source, target, model) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    with Session(source) as source_session, Session(target) as target_session:
        for source_row in source_session.exec(select(model)).all():
            if target_session.get(model, str(source_row.id)) is not None:
                skipped += 1
                continue
            target_session.add(model.model_validate(source_row.model_dump()))
            inserted += 1
        target_session.commit()
    return inserted, skipped


def _backup_rows(target, model, case_type: str) -> int:
    backed_up = 0
    with Session(target) as session:
        for row in session.exec(select(model)).all():
            image = _image_bytes(row.image_data)
            if image and image_store.backup_image(str(row.id), image):
                backed_up += 1
            if db_queries._backup_case_data(row, case_type) is None:
                continue
    return backed_up


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL must point to the destination PostgreSQL database")
    source_path = Path(__file__).resolve().parents[1] / "sqlite_database.db"
    source = create_engine(f"sqlite:///{source_path.as_posix()}")
    db_queries.create_db()

    registered = _copy_table(source, db_queries.engine, RegisteredCases)
    public = _copy_table(source, db_queries.engine, PublicSubmissions)
    registered_backups = _backup_rows(db_queries.engine, RegisteredCases, "registered")
    public_backups = _backup_rows(db_queries.engine, PublicSubmissions, "public")

    with Session(db_queries.engine) as session:
        registered_total = len(session.exec(select(RegisteredCases)).all())
        public_total = len(session.exec(select(PublicSubmissions)).all())
    print(f"registered inserted={registered[0]} skipped={registered[1]} total={registered_total}")
    print(f"public inserted={public[0]} skipped={public[1]} total={public_total}")
    print(f"Google Drive image backups attempted: registered={registered_backups}, public={public_backups}")


if __name__ == "__main__":
    main()