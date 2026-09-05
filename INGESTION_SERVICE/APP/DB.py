import os
import psycopg

DB_DSN = os.environ.get(
    "DATABASE_URL_PSYCOPG",
    "dbname=ekrs user=ekrs password=ekrs_dev_password host=localhost port=5432",
)


def get_connection():
    return psycopg.connect(DB_DSN)
