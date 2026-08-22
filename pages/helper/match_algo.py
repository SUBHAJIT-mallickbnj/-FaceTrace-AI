import json
from collections import defaultdict

import numpy as np
import pandas as pd
import pages.helper.db_queries as db_queries

IDENTITY_FEATURE_LENGTH = 128
IDENTITY_DISTANCE_THRESHOLD = 0.363
LEGACY_DISTANCE_THRESHOLD = 0.65


def get_public_cases_data(status=None):
    try:
        result = db_queries.fetch_public_cases(train_data=True, status=status)

        print(f"[DEBUG] get_public_cases_data: Fetched {len(result) if result else 0} public cases with status={status}")

        if not result:
            print("[DEBUG] get_public_cases_data: No public cases returned from DB")
            return None

        rows = [
            (label, feature)
            for label, face_mesh in result
            if (feature := _decode_feature(face_mesh)) is not None
        ]
        return pd.DataFrame(rows, columns=["label", "feature"])

    except Exception as e:
        print(f"[ERROR] get_public_cases_data failed: {str(e)}")
        return None


def get_registered_cases_data(status=None):
    try:
        from pages.helper.db_queries import engine, RegisteredCases
        from sqlmodel import Session, select

        with Session(engine) as session:
            result = session.exec(
                select(
                    RegisteredCases.id,
                    RegisteredCases.face_mesh,
                    RegisteredCases.status,
                )
            ).all()
            
            # Debug: Show total registered cases
            print(f"[DEBUG] get_registered_cases_data: Total registered cases in DB: {len(result)}")
            
            if status is not None:
                result = [row for row in result if row[2] == status]
            if not result:
                print(f"[WARNING] get_registered_cases_data: No registered cases found with status={status}")
                return None
            rows = [
                (label, feature)
                for label, face_mesh, _ in result
                if (feature := _decode_feature(face_mesh)) is not None
            ]
            return pd.DataFrame(rows, columns=["label", "feature"])
    except Exception as e:
        print(f"[ERROR] get_registered_cases_data failed: {str(e)}")
        return None


def _decode_feature(face_mesh):
    try:
        if isinstance(face_mesh, str):
            face_mesh = json.loads(face_mesh)
        if isinstance(face_mesh, dict):
            face_mesh = face_mesh.get("embedding") or face_mesh.get("landmarks")
        feature = np.asarray(face_mesh, dtype=np.float32).reshape(-1)
        return feature if feature.size else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _distance(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size != right.size:
        return None
    if left.size == IDENTITY_FEATURE_LENGTH:
        left_norm = np.linalg.norm(left)
        right_norm = np.linalg.norm(right)
        if left_norm == 0 or right_norm == 0:
            return None
        return 1.0 - float(np.dot(left, right) / (left_norm * right_norm))
    return float(np.linalg.norm(left - right))


def match(distance_threshold=IDENTITY_DISTANCE_THRESHOLD):
    matched_images = defaultdict(list)
    diagnostics = []
    public_cases = get_public_cases_data("NF")
    registered_cases = get_registered_cases_data("NF")

    print(f"[DEBUG] match: public_cases is None: {public_cases is None}")
    print(f"[DEBUG] match: registered_cases is None: {registered_cases is None}")

    if public_cases is None or registered_cases is None:
        message = "No unresolved public sightings or registered cases available"
        print(f"[INFO] {message}")
        return {"status": True, "result": {}, "message": message}

    for public_row in public_cases.itertuples(index=False):
        pub_label, public_feature = public_row
        closest_distance = None
        closest_label = None
        for registered_row in registered_cases.itertuples(index=False):
            reg_label, registered_feature = registered_row
            candidate_distance = _distance(public_feature, registered_feature)
            if candidate_distance is not None and (
                closest_distance is None or candidate_distance < closest_distance
            ):
                closest_distance = candidate_distance
                closest_label = reg_label
        if closest_distance is None:
            continue
        threshold = distance_threshold if public_feature.size == IDENTITY_FEATURE_LENGTH else LEGACY_DISTANCE_THRESHOLD
        diagnostics.append(
            {
                "public_id": pub_label,
                "registered_id": closest_label,
                "distance": closest_distance,
                "threshold": threshold,
                "matched": closest_distance <= threshold,
            }
        )
        print(f"[DEBUG] Public case {pub_label}: closest_distance={closest_distance:.4f}, threshold={threshold}")
        if closest_distance <= threshold:
            matched_images[closest_label].append((pub_label, closest_distance))
            print(f"[INFO] Match found: public {pub_label} -> registered {closest_label} (distance={closest_distance:.4f})")

    print(f"[DEBUG] match: Total matches found: {len(matched_images)}")
    return {
        "status": True,
        "result": dict(matched_images),
        "diagnostics": diagnostics,
    }


if __name__ == "__main__":
    result = match()
    print(result)
