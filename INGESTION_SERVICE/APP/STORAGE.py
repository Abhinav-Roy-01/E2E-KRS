"""
MinIO client — stores raw file bytes under key = raw_documents.id (UUID),
same convention as before: never trust the raw client filename as a storage
key, to avoid collisions/path traversal.
"""
import os
from io import BytesIO
from minio import Minio

MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "ekrs_minio")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "ekrs_minio_dev_password")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "ekrs-documents")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False,  # dev only
        )
    return _client


def ensure_bucket():
    client = _get_client()
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)


def upload_file(object_name: str, file_bytes: bytes, content_type: str = "application/octet-stream"):
    _get_client().put_object(
        MINIO_BUCKET, object_name, BytesIO(file_bytes),
        length=len(file_bytes), content_type=content_type,
    )
