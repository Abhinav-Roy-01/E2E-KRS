"""Shared connection helpers: .env loading + wait-for-service retry loops.

Dockerized databases take a few seconds to become ready after
`docker compose up`. Every seed script calls its wait_*() before seeding so
there is no race condition (healthchecks in Compose are a second layer of
protection).
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env() -> None:
    from dotenv import load_dotenv
    load_dotenv(project_root() / ".env")


def _retry(name: str, fn, attempts: int = 30, delay: float = 2.0) -> bool:
    print(f"  [wait] checking {name} ...")
    for i in range(1, attempts + 1):
        try:
            fn()
            print(f"  [ok]   {name} reachable")
            return True
        except Exception as exc:  # noqa: BLE001 - any connection error means not ready
            print(f"  [..]   {name} not ready ({i}/{attempts}): {type(exc).__name__}: {exc}")
            time.sleep(delay)
    return False


def wait_mysql() -> bool:
    import pymysql

    cfg = {
        "host": os.environ["MYSQL_HOST"],
        "port": int(os.environ["MYSQL_PORT"]),
        "user": os.environ["MYSQL_USER"],
        "password": os.environ["MYSQL_PASSWORD"],
        "database": os.environ["MYSQL_DATABASE"],
        "connect_timeout": 3,
    }

    def ping() -> None:
        conn = pymysql.connect(**cfg)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()

    return _retry("MySQL", ping)


def wait_postgres() -> bool:
    import psycopg

    cfg = {
        "host": os.environ["POSTGRES_HOST"],
        "port": int(os.environ["POSTGRES_PORT"]),
        "user": os.environ["POSTGRES_USER"],
        "password": os.environ["POSTGRES_PASSWORD"],
        "dbname": os.environ["COURSES_DB"],
        "connect_timeout": 3,
    }

    def ping() -> None:
        conn = psycopg.connect(**cfg)
        conn.close()

    return _retry("PostgreSQL", ping)


def wait_mongo() -> bool:
    from pymongo import MongoClient

    host = os.environ["MONGO_HOST"]
    port = int(os.environ["MONGO_PORT"])

    def ping() -> None:
        client = MongoClient(host, port, serverSelectionTimeoutMS=3000)
        try:
            client.admin.command("ping")
        finally:
            client.close()

    return _retry("MongoDB", ping)
