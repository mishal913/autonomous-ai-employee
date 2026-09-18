import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv()


# ==========================================================
# DATABASE SETTINGS
# ==========================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "ai_employee")
DB_USER = os.getenv("DB_USER", "ai_employee_user")
DB_PASSWORD = os.getenv("DB_PASSWORD")


if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD was not found in your .env file."
    )


# ==========================================================
# DATABASE URL
# ==========================================================

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)


# ==========================================================
# ENGINE
# ==========================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)


# ==========================================================
# SESSION FACTORY
# ==========================================================

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


# ==========================================================
# SQLALCHEMY BASE CLASS
# ==========================================================

class Base(DeclarativeBase):
    pass


# ==========================================================
# CREATE TABLES
# ==========================================================

def create_tables():

    from app import models

    Base.metadata.create_all(
        bind=engine
    )


# ==========================================================
# CONNECTION TEST
# ==========================================================

def test_connection():

    with engine.connect() as connection:

        result = connection.execute(
            text(
                "SELECT current_database(), current_user"
            )
        )

        row = result.fetchone()

        return {
            "database": row[0],
            "user": row[1],
        }