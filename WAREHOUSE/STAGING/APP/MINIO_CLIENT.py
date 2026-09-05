"""
Downloads a raw document's bytes from MinIO by its storage_key
(raw_documents.storage_key, set by INGESTION_SERVICE at upload time).
"""
import os
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
            secure=False,
        )
    return _client


def download_to_path(storage_key: str, local_path: str):
    _get_client().fget_object(MINIO_BUCKET, storage_key, local_path)
