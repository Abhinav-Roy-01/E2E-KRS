"""
Bootstrap a real user with a real API key. This is how the FIRST users get
into the system -- there's no self-signup, deliberately (a government
document system shouldn't let anyone hand themselves an account).

The raw key is printed ONCE, here, and never again -- only its sha256 hash
is stored in the database (users.api_key_hash). Losing the printed key
means generating a new one (re-run with --regenerate), not recovering it.

Usage:
    python CREATE_USER.py --name "Abhinav Roy" --email abhinav@example.gov.in \
        --role admin --department Engineering
"""
import argparse
import hashlib
import secrets

from dotenv import load_dotenv
load_dotenv()

from DB import get_connection

VALID_ROLES = ("admin", "department_head", "employee")


def create_user(name: str, email: str, role: str, department: str | None) -> None:
    if role not in VALID_ROLES:
        raise SystemExit(f"--role must be one of {VALID_ROLES}, got '{role}'")

    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (name, email, role, department, api_key_hash)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name, email, role, department, key_hash),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    print("=" * 60)
    print(f"User created: {name} <{email}> ({role}, {department or 'no department'})")
    print(f"user.id = {user_id}")
    print()
    print("API key (SAVE THIS NOW -- it will not be shown again):")
    print(f"  {raw_key}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=VALID_ROLES)
    parser.add_argument("--department", default=None)
    args = parser.parse_args()
    create_user(args.name, args.email, args.role, args.department)
