"""
Physically moves a document's object in MinIO from its ingestion-time key
(a random UUID, meaningless to a human browsing the bucket) to its routed
key (e.g. Engineering/Internal/Reports/2026/notice.pdf) once it's promoted
to document_mart.

This is the actual "routing engine solves document overload" step -- until
this module existed, storage_path was only a string in a database column;
the file itself never moved. A human (or any tool) browsing MinIO's console
directly, with no database access at all, can now find a document by
walking department -> sensitivity -> doc_type -> year, which is the whole
point of the routing-engine pitch.
"""
import os

from minio import Minio
from minio.commonconfig import CopySource

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


def move_object(source_key: str, dest_key: str) -> None:
    """
    Copy source_key -> dest_key, then delete source_key. MinIO (like S3) has
    no atomic rename, so this is copy-then-delete -- fine for this project's
    scale, but means a crash between the two steps could leave the object at
    BOTH keys (rare, and harmless: a re-run of DOCUMENT_MART won't reprocess
    an already-promoted intermediate_documents row, so this doesn't double-
    promote, just leaves an orphaned copy at the old key worth a periodic
    cleanup pass -- not built here, noted as a known gap).
    """
    if source_key == dest_key:
        return
    client = _get_client()
    client.copy_object(MINIO_BUCKET, dest_key, CopySource(MINIO_BUCKET, source_key))
    client.remove_object(MINIO_BUCKET, source_key)
