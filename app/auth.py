import hashlib
import hmac
import os
import secrets

from datetime import datetime, timedelta, timezone

import jwt

from sqlalchemy import text

from app.database import SessionLocal


# ============================================================
# CONFIGURATION
# ============================================================

JWT_ALGORITHM = "HS256"

TOKEN_HOURS = int(
    os.getenv(
        "AUTH_TOKEN_HOURS",
        "8",
    )
)

PASSWORD_ITERATIONS = int(
    os.getenv(
        "AUTH_PBKDF2_ITERATIONS",
        "600000",
    )
)

COOKIE_NAME = (
    "ai_employee_access_token"
)


# ============================================================
# DATABASE SCHEMA
# ============================================================

def ensure_auth_schema() -> None:
    """
    Create the authentication table if it does not exist.

    We keep auth isolated from the existing business tables so
    the current working database models do not need to be changed.
    """

    db = SessionLocal()

    try:
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(320) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role VARCHAR(32) NOT NULL
                        CHECK (role IN ('admin', 'operator')),
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_login_at TIMESTAMPTZ NULL
                )
                """
            )
        )

        db.commit()

    finally:
        db.close()


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(
    password: str,
) -> str:
    """
    PBKDF2-HMAC-SHA256 password hashing using only the
    Python standard library.

    Stored format:
    pbkdf2_sha256$iterations$salt_hex$digest_hex
    """

    if len(password) < 10:
        raise ValueError(
            "Password must contain at least 10 characters."
        )

    salt = secrets.token_bytes(32)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )

    return (
        f"pbkdf2_sha256$"
        f"{PASSWORD_ITERATIONS}$"
        f"{salt.hex()}$"
        f"{digest.hex()}"
    )


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:

    try:
        (
            algorithm,
            iterations_text,
            salt_hex,
            expected_hex,
        ) = stored_hash.split(
            "$",
            3,
        )

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(
            iterations_text
        )

        salt = bytes.fromhex(
            salt_hex
        )

        expected = bytes.fromhex(
            expected_hex
        )

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        return hmac.compare_digest(
            candidate,
            expected,
        )

    except Exception:
        return False


# ============================================================
# JWT
# ============================================================

def get_jwt_secret() -> str:

    secret = os.getenv(
        "APP_JWT_SECRET"
    )

    if not secret:
        raise RuntimeError(
            "APP_JWT_SECRET is missing from .env. "
            "Generate a strong random secret before using authentication."
        )

    if len(secret) < 32:
        raise RuntimeError(
            "APP_JWT_SECRET must be at least 32 characters long."
        )

    return secret


def create_access_token(
    user: dict,
) -> tuple[str, datetime]:

    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now
        +
        timedelta(
            hours=TOKEN_HOURS
        )
    )

    payload = {
        "sub":
            str(
                user["id"]
            ),

        "email":
            user["email"],

        "role":
            user["role"],

        "iat":
            now,

        "exp":
            expires_at,

        "iss":
            "autonomous-ai-employee",
    }

    token = jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )

    return (
        token,
        expires_at,
    )


def decode_access_token(
    token: str,
) -> dict | None:

    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[
                JWT_ALGORITHM
            ],
            issuer=(
                "autonomous-ai-employee"
            ),
        )

        return payload

    except (
        jwt.ExpiredSignatureError,
        jwt.InvalidTokenError,
        RuntimeError,
    ):
        return None


# ============================================================
# USERS
# ============================================================

def normalize_email(
    email: str,
) -> str:

    return (
        email
        .strip()
        .lower()
    )


def get_user_by_email(
    email: str,
) -> dict | None:

    ensure_auth_schema()

    db = SessionLocal()

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT
                        id,
                        email,
                        password_hash,
                        role,
                        is_active,
                        created_at,
                        last_login_at
                    FROM app_users
                    WHERE email = :email
                    LIMIT 1
                    """
                ),
                {
                    "email":
                        normalize_email(
                            email
                        )
                },
            )
            .mappings()
            .first()
        )

        if not row:
            return None

        return dict(
            row
        )

    finally:
        db.close()


def get_user_by_id(
    user_id: int,
) -> dict | None:

    ensure_auth_schema()

    db = SessionLocal()

    try:
        row = (
            db.execute(
                text(
                    """
                    SELECT
                        id,
                        email,
                        role,
                        is_active,
                        created_at,
                        last_login_at
                    FROM app_users
                    WHERE id = :user_id
                    LIMIT 1
                    """
                ),
                {
                    "user_id":
                        user_id
                },
            )
            .mappings()
            .first()
        )

        if not row:
            return None

        return dict(
            row
        )

    finally:
        db.close()


def create_user(
    email: str,
    password: str,
    role: str,
) -> dict:

    ensure_auth_schema()

    email = normalize_email(
        email
    )

    if (
        not email
        or
        "@"
        not in email
    ):
        raise ValueError(
            "A valid email address is required."
        )

    if role not in {
        "admin",
        "operator",
    }:
        raise ValueError(
            "Role must be 'admin' or 'operator'."
        )

    password_hash = (
        hash_password(
            password
        )
    )

    db = SessionLocal()

    try:
        row = (
            db.execute(
                text(
                    """
                    INSERT INTO app_users (
                        email,
                        password_hash,
                        role,
                        is_active
                    )
                    VALUES (
                        :email,
                        :password_hash,
                        :role,
                        TRUE
                    )
                    RETURNING
                        id,
                        email,
                        role,
                        is_active,
                        created_at,
                        last_login_at
                    """
                ),
                {
                    "email":
                        email,

                    "password_hash":
                        password_hash,

                    "role":
                        role,
                },
            )
            .mappings()
            .first()
        )

        db.commit()

        return dict(
            row
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def list_users() -> list[dict]:

    ensure_auth_schema()

    db = SessionLocal()

    try:
        rows = (
            db.execute(
                text(
                    """
                    SELECT
                        id,
                        email,
                        role,
                        is_active,
                        created_at,
                        last_login_at
                    FROM app_users
                    ORDER BY created_at ASC
                    """
                )
            )
            .mappings()
            .all()
        )

        return [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()


def set_user_active(
    user_id: int,
    is_active: bool,
) -> dict | None:

    ensure_auth_schema()

    db = SessionLocal()

    try:
        row = (
            db.execute(
                text(
                    """
                    UPDATE app_users
                    SET is_active = :is_active
                    WHERE id = :user_id
                    RETURNING
                        id,
                        email,
                        role,
                        is_active,
                        created_at,
                        last_login_at
                    """
                ),
                {
                    "user_id":
                        user_id,

                    "is_active":
                        is_active,
                },
            )
            .mappings()
            .first()
        )

        db.commit()

        if not row:
            return None

        return dict(
            row
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def update_last_login(
    user_id: int,
) -> None:

    db = SessionLocal()

    try:
        db.execute(
            text(
                """
                UPDATE app_users
                SET last_login_at = NOW()
                WHERE id = :user_id
                """
            ),
            {
                "user_id":
                    user_id
            },
        )

        db.commit()

    finally:
        db.close()


# ============================================================
# INITIAL ADMIN
# ============================================================

def ensure_initial_admin() -> None:
    """
    Bootstrap one admin from .env only when that email does
    not already exist.

    The plaintext password is never stored in PostgreSQL.
    """

    ensure_auth_schema()

    email = os.getenv(
        "APP_ADMIN_EMAIL"
    )

    password = os.getenv(
        "APP_ADMIN_PASSWORD"
    )

    if (
        not email
        or
        not password
    ):
        return

    existing = get_user_by_email(
        email
    )

    if existing:
        return

    create_user(
        email=email,
        password=password,
        role="admin",
    )
