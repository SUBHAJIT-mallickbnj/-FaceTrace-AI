import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from sqlmodel import SQLModel, Session, create_engine, select

from pages.helper import db_queries
from pages.helper.data_models import RegisteredCases


class DuplicateCaseSaveTests(unittest.TestCase):
    def test_register_new_case_retries_with_new_id_on_duplicate(self):
        with TemporaryDirectory() as tmpdir:
            temp_db = Path(tmpdir) / "test.db"
            temp_engine = create_engine(f"sqlite:///{temp_db}")
            SQLModel.metadata.create_all(temp_engine)

            with patch.object(db_queries, "engine", temp_engine):
                first_case = RegisteredCases(
                    id="duplicate-id",
                    submitted_by="tester",
                    name="First",
                    complainant_name="Complainant",
                    complainant_mobile="1234567890",
                    adhaar_card="123456789012",
                    last_seen="Delhi",
                    address="Addr",
                    city="Delhi",
                    face_mesh="[]",
                    status="NF",
                    birth_marks="",
                    matched_with="",
                )
                db_queries.register_new_case(first_case)

                second_case = RegisteredCases(
                    id="duplicate-id",
                    submitted_by="tester",
                    name="Second",
                    complainant_name="Complainant",
                    complainant_mobile="1234567890",
                    adhaar_card="123456789012",
                    last_seen="Delhi",
                    address="Addr",
                    city="Delhi",
                    face_mesh="[]",
                    status="NF",
                    birth_marks="",
                    matched_with="",
                )

                db_queries.register_new_case(second_case)

                with Session(temp_engine) as session:
                    rows = session.exec(select(RegisteredCases)).all()
                    self.assertEqual(len(rows), 2)
                    self.assertNotEqual(rows[0].id, rows[1].id)

                temp_engine.dispose()
                if temp_db.exists():
                    temp_db.unlink()


if __name__ == "__main__":
    unittest.main()
