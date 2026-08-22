import os
import io
import json


def _setting(name: str, default=None):
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets.get(name, default)
    except Exception:
        return default


def _settings():
    """Read optional Google Drive backup settings."""
    credentials = _setting("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    folder_id = _setting("GOOGLE_DRIVE_FOLDER_ID")
    if not credentials or not folder_id:
        return None
    try:
        if isinstance(credentials, str):
            credentials = json.loads(credentials)
        return {"credentials": credentials, "folder_id": folder_id}
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _client(settings):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_info(
        settings["credentials"],
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _file_name(case_id: str) -> str:
    return f"case-images/{case_id}.jpg"


def backup_image(case_id: str, image_bytes: bytes) -> bool:
    settings = _settings()
    if settings is None:
        return False
    try:
        from googleapiclient.http import MediaIoBaseUpload

        client = _client(settings)
        name = _file_name(case_id)
        query = (
            f"name = '{name}' and '{settings['folder_id']}' in parents "
            "and trashed = false"
        )
        files = client.files().list(q=query, fields="files(id)").execute().get("files", [])
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg")
        metadata = {"name": name, "parents": [settings["folder_id"]]}
        if files:
            client.files().update(fileId=files[0]["id"], media_body=media).execute()
        else:
            client.files().create(body=metadata, media_body=media, fields="id").execute()
        return True
    except Exception:
        return False


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
        files = client.files().list(q=query, fields="files(id)").execute().get("files", [])
        if not files:
            return None
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(
            buffer, client.files().get_media(fileId=files[0]["id"])
        )
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
    except Exception:
        return None
