import os
import io
import json
import re
from urllib.parse import parse_qs, urlsplit


_last_error = None


def _setting(name: str, default=None):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        value = st.secrets.get(name)
        if value:
            return value
        section_names = {"google_drive", "GOOGLE_DRIVE"}
        for section_name in section_names:
            section = st.secrets.get(section_name)
            if not section:
                continue
            for key in (name, name.lower(), name.removeprefix("GOOGLE_DRIVE_").lower()):
                value = section.get(key) if hasattr(section, "get") else None
                if value:
                    return value
        return default
    except Exception:
        return default


def _folder_id(value) -> str | None:
    """Accept a Drive folder ID or a folder URL pasted into secrets."""
    if not value:
        return None
    value = str(value).strip()
    if "drive.google.com" not in value:
        return value
    parsed = urlsplit(value)
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    match = re.search(r"/folders/([A-Za-z0-9_-]+)", parsed.path)
    return query_id or (match.group(1) if match else None)


def _settings():
    """Read optional Google Drive service-account or OAuth settings."""
    refresh_token = _setting("GOOGLE_DRIVE_REFRESH_TOKEN")
    client_id = _setting("GOOGLE_DRIVE_CLIENT_ID")
    client_secret = _setting("GOOGLE_DRIVE_CLIENT_SECRET")
    credentials = _setting("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    folder_id = _folder_id(_setting("GOOGLE_DRIVE_FOLDER_ID"))
    if not folder_id:
        return None
    if refresh_token and client_id and client_secret:
        return {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "folder_id": folder_id,
        }
    if not credentials:
        return None
    try:
        if isinstance(credentials, str):
            credentials = json.loads(credentials)
        return {"credentials": credentials, "folder_id": folder_id}
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _client(settings):
    from googleapiclient.discovery import build

    if "refresh_token" in settings:
        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=None,
            refresh_token=settings["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings["client_id"],
            client_secret=settings["client_secret"],
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
    else:
        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_info(
            settings["credentials"],
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _request_kwargs(settings):
    """Use shared-drive flags when the configured folder belongs to one."""
    return {"supportsAllDrives": True, "includeItemsFromAllDrives": True}


def _write_request_kwargs():
    """Return only parameters accepted by Drive create/update requests."""
    return {"supportsAllDrives": True}


def _record_error(operation: str, exc: Exception):
    global _last_error
    _last_error = f"{operation}: {exc}"
    print(f"[WARNING] Google Drive {_last_error}")


def _file_name(case_id: str) -> str:
    return f"case-images/{case_id}.jpg"


def _data_file_name(case_type: str, case_id: str) -> str:
    return f"case-data/{case_type}-{case_id}.json"


def backup_image(case_id: str, image_bytes: bytes) -> bool:
    global _last_error
    _last_error = None
    settings = _settings()
    if settings is None:
        _record_error(
            "image backup is not configured",
            ValueError(
                "set GOOGLE_DRIVE_FOLDER_ID and either OAuth credentials "
                "or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"
            ),
        )
        return False
    try:
        from googleapiclient.http import MediaIoBaseUpload

        client = _client(settings)
        name = _file_name(case_id)
        query = (
            f"name = '{name}' and '{settings['folder_id']}' in parents "
            "and trashed = false"
        )
        files = client.files().list(
            q=query,
            fields="files(id)",
            **_request_kwargs(settings),
        ).execute().get("files", [])
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg")
        metadata = {"name": name, "parents": [settings["folder_id"]]}
        if files:
            client.files().update(
                fileId=files[0]["id"],
                media_body=media,
                **_write_request_kwargs(),
            ).execute()
        else:
            client.files().create(
                body=metadata,
                media_body=media,
                fields="id",
                **_write_request_kwargs(),
            ).execute()
        return True
    except Exception as exc:
        _record_error(f"image backup failed for {case_id}", exc)
        return False


def backup_case_data(case_type: str, case_id: str, data: dict) -> bool:
    """Back up case metadata as a JSON file in the configured Drive folder."""
    global _last_error
    _last_error = None
    settings = _settings()
    if settings is None:
        _record_error(
            "data backup is not configured",
            ValueError(
                "set GOOGLE_DRIVE_FOLDER_ID and either OAuth credentials "
                "or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON"
            ),
        )
        return False
    try:
        from googleapiclient.http import MediaIoBaseUpload

        client = _client(settings)
        name = _data_file_name(case_type, case_id)
        query = (
            f"name = '{name}' and '{settings['folder_id']}' in parents "
            "and trashed = false"
        )
        files = client.files().list(
            q=query,
            fields="files(id)",
            **_request_kwargs(settings),
        ).execute().get("files", [])
        payload = json.dumps(data, ensure_ascii=True, default=str).encode("utf-8")
        media = MediaIoBaseUpload(
            io.BytesIO(payload), mimetype="application/json", resumable=False
        )
        metadata = {"name": name, "parents": [settings["folder_id"]]}
        if files:
            client.files().update(
                fileId=files[0]["id"],
                media_body=media,
                **_request_kwargs(settings),
            ).execute()
        else:
            client.files().create(
                body=metadata,
                media_body=media,
                fields="id",
                **_request_kwargs(settings),
            ).execute()
        return True
    except Exception as exc:
        _record_error(f"data backup failed for {case_id}", exc)
        return False


def last_error() -> str | None:
    return _last_error


def backup_configured() -> bool:
    """Return whether a complete Drive credential configuration is available."""
    return _settings() is not None


def restore_image(case_id: str) -> bytes | None:
    settings = _settings()
    if settings is None:
        return None
    try:
        from googleapiclient.http import MediaIoBaseDownload

        client = _client(settings)
        query = (
            f"name = '{_file_name(case_id)}' and '{settings['folder_id']}' in parents "
            "and trashed = false"
        )
        files = client.files().list(
            q=query,
            fields="files(id)",
            **_request_kwargs(settings),
        ).execute().get("files", [])
        if not files:
            return None
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            buffer,
            client.files().get_media(
                fileId=files[0]["id"], **_write_request_kwargs()
            ),
        )
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
    except Exception as exc:
        print(f"[WARNING] Google Drive restore failed for {case_id}: {exc}")
        return None
