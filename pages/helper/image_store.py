import os



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
    """Read optional S3-compatible backup settings without requiring them locally."""
    bucket = _setting("IMAGE_BACKUP_BUCKET")
    access_key = _setting("IMAGE_BACKUP_ACCESS_KEY")
    secret_key = _setting("IMAGE_BACKUP_SECRET_KEY")
    if not all((bucket, access_key, secret_key)):
        return None
    return {
        "bucket": bucket,
        "access_key": access_key,
        "secret_key": secret_key,
        "endpoint_url": _setting("IMAGE_BACKUP_ENDPOINT_URL"),
        "region_name": _setting("IMAGE_BACKUP_REGION", "auto"),
    }


def backup_image(case_id: str, image_bytes: bytes) -> bool:
    settings = _settings()
    if settings is None:
        return False
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings["endpoint_url"],
            region_name=settings["region_name"],
            aws_access_key_id=settings["access_key"],
            aws_secret_access_key=settings["secret_key"],
        )
        client.put_object(
            Bucket=settings["bucket"],
            Key=f"case-images/{case_id}.jpg",
            Body=image_bytes,
            ContentType="image/jpeg",
        )
        return True
    except Exception:
        return False


def restore_image(case_id: str) -> bytes | None:
    settings = _settings()
    if settings is None:
        return None
    try:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings["endpoint_url"],
            region_name=settings["region_name"],
            aws_access_key_id=settings["access_key"],
            aws_secret_access_key=settings["secret_key"],
        )
        response = client.get_object(
            Bucket=settings["bucket"], Key=f"case-images/{case_id}.jpg"
        )
        return response["Body"].read()
    except Exception:
        return None
